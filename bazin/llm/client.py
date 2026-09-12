"""LLM access for every stage: structured outputs, Message Batches, cost tracking, and a heuristic fallback.

`LLM.structured()` returns a validated Pydantic object for one request; `run_batch()` does the same for
thousands through the Batches API at half price. `HeuristicLLM` implements the same interface with
deterministic rules over the taxonomy so the pipeline runs without an API key (tests, dry runs, outages).
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, Field

from ..config import MODEL_PRICES, Settings, get_settings
from ..models import (
    ClusterLabel, ColorShare, CommerceSignals, ConceptHit, ContactOut, Enrichment, JudgeVerdict, LocationOut,
    LocationQuery, OfferOut, ParsedQuery, PostClassification, PriceMention, PriceOut, RelevanceVerdict, ScoreNarrative,
    BudgetOut,
)

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class QueryExpansion(BaseModel):
    phrasings: list[str] = Field(default_factory=list, max_length=5)


class SameBusiness(BaseModel):
    same_business: bool
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(max_length=200)


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class BatchItem:
    custom_id: str
    user_text: str
    images: list[bytes | str] = field(default_factory=list)


def cost_for(model: str, input_tokens: int, output_tokens: int, cache_read: int = 0, batch: bool = False) -> float:
    inp, out = MODEL_PRICES.get(model, (5.0, 25.0))
    mult = 0.5 if batch else 1.0
    return ((input_tokens * inp) + (output_tokens * out) + (cache_read * inp * 0.1)) / 1_000_000 * mult


def sniff_media_type(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def content_blocks(user_text: str, images: list[bytes | str] | None) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for img in images or []:
        if isinstance(img, (bytes, bytearray)):
            blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": sniff_media_type(bytes(img)), "data": base64.standard_b64encode(bytes(img)).decode()},
            })
        elif isinstance(img, str) and img.startswith("http"):
            blocks.append({"type": "image", "source": {"type": "url", "url": img}})
    blocks.append({"type": "text", "text": user_text})
    return blocks


class LLM:
    """Real client. `recorder` receives one dict per call/batch item for the llm_calls table."""

    def __init__(self, settings: Settings | None = None, recorder: Callable[[dict[str, Any]], None] | None = None, spent_usd: float = 0.0):
        self.settings = settings or get_settings()
        self.recorder = recorder
        self.spent_usd = spent_usd
        self._client: Any = None

    @property
    def client(self):  # lazy so the heuristic subclass never imports the SDK
        if self._client is None:
            import anthropic

            kwargs: dict[str, Any] = {}
            if self.settings.anthropic_api_key:
                kwargs["api_key"] = self.settings.anthropic_api_key
            self._client = anthropic.Anthropic(**kwargs)
        return self._client

    # ------------------------------------------------------------ helpers

    def _check_budget(self) -> None:
        if self.spent_usd >= self.settings.llm_budget_usd:
            raise BudgetExceeded(f"LLM spend {self.spent_usd:.2f} USD reached the budget {self.settings.llm_budget_usd:.2f}")

    def _record(self, stage: str, model: str, usage: Any, *, batch: bool, batch_id: str | None = None, custom_id: str | None = None) -> Usage:
        u = Usage(
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            cache_read_tokens=int(getattr(usage, "cache_read_input_tokens", 0) or 0),
        )
        u.cost_usd = cost_for(model, u.input_tokens, u.output_tokens, u.cache_read_tokens, batch)
        self.spent_usd += u.cost_usd
        if self.recorder:
            self.recorder({
                "stage": stage, "model": model, "batch_id": batch_id, "custom_id": custom_id,
                "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                "cache_read_tokens": u.cache_read_tokens, "cost_usd": u.cost_usd,
            })
        return u

    @staticmethod
    def _system_param(system: str | None) -> Any:
        if not system:
            return None
        return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    @staticmethod
    def _effort_config(model: str, effort: str) -> dict[str, Any]:
        # Haiku 4.5 rejects the effort parameter; Opus 5 and Sonnet 5 run adaptive thinking by default.
        return {} if model.startswith("claude-haiku") else {"effort": effort}

    # ------------------------------------------------------------ single request

    def structured(self, stage: str, *, system: str | None, user_text: str, schema: type[T], effort: str = "medium",
                   images: list[bytes | str] | None = None, max_tokens: int = 4096) -> T:
        self._check_budget()
        model = self.settings.model_for(stage)
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": content_blocks(user_text, images)}],
            "output_format": schema,
        }
        sys_param = self._system_param(system)
        if sys_param:
            kwargs["system"] = sys_param
        eff = self._effort_config(model, effort)
        if eff:
            kwargs["output_config"] = eff
        resp = self.client.messages.parse(**kwargs)
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"{stage}: model refused ({getattr(resp.stop_details, 'category', None)})")
        self._record(stage, model, resp.usage, batch=False)
        parsed = resp.parsed_output
        if parsed is None:
            raise ValueError(f"{stage}: no structured output returned")
        return parsed

    # ------------------------------------------------------------ batches

    def submit_batch(self, stage: str, items: list[BatchItem], schema: type[T], *, system: str | None,
                     effort: str = "low", max_tokens: int = 2048) -> str:
        from anthropic.lib._parse._transform import transform_schema
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request

        self._check_budget()
        model = self.settings.model_for(stage)
        fmt = {"type": "json_schema", "schema": transform_schema(schema)}
        sys_param = self._system_param(system)
        requests = []
        for it in items:
            params: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": content_blocks(it.user_text, it.images)}],
                "output_config": {"format": fmt, **self._effort_config(model, effort)},
            }
            if sys_param:
                params["system"] = sys_param
            requests.append(Request(custom_id=it.custom_id, params=MessageCreateParamsNonStreaming(**params)))
        batch = self.client.messages.batches.create(requests=requests)
        log.info("submitted batch %s for %s with %d items", batch.id, stage, len(items))
        return batch.id

    def batch_status(self, batch_id: str) -> tuple[str, dict[str, int]]:
        b = self.client.messages.batches.retrieve(batch_id)
        c = b.request_counts
        return b.processing_status, {"processing": c.processing, "succeeded": c.succeeded, "errored": c.errored, "canceled": c.canceled, "expired": c.expired}

    def collect_batch(self, batch_id: str, stage: str, schema: type[T]) -> dict[str, T | Exception]:
        model = self.settings.model_for(stage)
        out: dict[str, T | Exception] = {}
        for result in self.client.messages.batches.results(batch_id):
            rtype = result.result.type
            if rtype == "succeeded":
                msg = result.result.message
                self._record(stage, model, msg.usage, batch=True, batch_id=batch_id, custom_id=result.custom_id)
                if msg.stop_reason == "refusal":
                    out[result.custom_id] = RuntimeError("refusal")
                    continue
                text = next((b.text for b in msg.content if b.type == "text"), "")
                try:
                    out[result.custom_id] = schema.model_validate_json(text)
                except Exception as e:  # noqa: BLE001
                    out[result.custom_id] = e
            elif rtype == "errored":
                out[result.custom_id] = RuntimeError(f"errored: {result.result.error.type}")
            else:
                out[result.custom_id] = RuntimeError(rtype)
        return out

    def run_batch(self, stage: str, items: list[BatchItem], schema: type[T], *, system: str | None, effort: str = "low",
                  max_tokens: int = 2048, poll_seconds: float = 30.0, timeout_seconds: float = 6 * 3600,
                  chunk_size: int = 5000) -> dict[str, T | Exception]:
        """Submit, wait, collect. Falls back to one-by-one calls for very small item counts."""
        if not items:
            return {}
        if not self.settings.use_batches or len(items) < 5:
            out: dict[str, T | Exception] = {}
            for it in items:
                try:
                    out[it.custom_id] = self.structured(stage, system=system, user_text=it.user_text, schema=schema, effort=effort, images=it.images, max_tokens=max_tokens)
                except Exception as e:  # noqa: BLE001
                    out[it.custom_id] = e
            return out
        results: dict[str, T | Exception] = {}
        for i in range(0, len(items), chunk_size):
            chunk = items[i : i + chunk_size]
            batch_id = self.submit_batch(stage, chunk, schema, system=system, effort=effort, max_tokens=max_tokens)
            deadline = time.time() + timeout_seconds
            while True:
                status, counts = self.batch_status(batch_id)
                if status == "ended":
                    break
                if time.time() > deadline:
                    raise TimeoutError(f"batch {batch_id} did not finish in {timeout_seconds}s")
                time.sleep(poll_seconds)
            results.update(self.collect_batch(batch_id, stage, schema))
        return results


# ======================================================================= heuristic fallback


FR_WORDS = {"le", "la", "les", "des", "pour", "avec", "sur", "chez", "disponible", "livraison", "prix", "commande", "nous", "vous", "et", "une", "un"}
EN_WORDS = {"the", "and", "for", "with", "available", "delivery", "price", "shipping", "order", "our", "your", "from", "to"}
IT_WORDS = {"il", "per", "con", "disponibile", "consegna", "prezzo", "spedizione", "abiti", "tessuti"}
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
SHIP_WORDS = ("livraison", "expédition", "expedition", "envoi", "ship", "shipping", "delivery", "livre", "livrons")
MAKER_WORDS = ("tailleur", "couturier", "couturière", "couture", "atelier", "tailor", "seamstress", "designer", "styliste", "maker", "make", "sur mesure", "bespoke")
BUY_WORDS = ("acheter", "achat", "buy", "where to buy", "vente", "boutique", "shop", "store", "magasin", "fabric", "tissu", "mètre", "yard")
CUSTOMER_WORDS = ("cliente", "client", "customer", "merci", "thank you", "mashallah", "fitting", "essayage", "livrée", "livré")


def detect_language(text: str) -> str:
    words = set(re.findall(r"[a-zàâçéèêëîïôûùüÿœ']+", (text or "").lower()))
    scores = {"fr": len(words & FR_WORDS), "en": len(words & EN_WORDS), "it": len(words & IT_WORDS)}
    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 else "unknown"


COUNTRY_ALIASES = {
    "sénégal": "SN", "senegal": "SN", "dakar": "SN", "mali": "ML", "bamako": "ML", "guinée": "GN", "guinea": "GN", "conakry": "GN",
    "gambie": "GM", "gambia": "GM", "banjul": "GM", "côte d'ivoire": "CI", "ivory coast": "CI", "abidjan": "CI", "bénin": "BJ", "benin": "BJ",
    "cotonou": "BJ", "togo": "TG", "lomé": "TG", "nigeria": "NG", "lagos": "NG", "kano": "NG", "abuja": "NG", "france": "FR", "paris": "FR",
    "lyon": "FR", "marseille": "FR", "usa": "US", "états-unis": "US", "etats-unis": "US", "united states": "US", "america": "US", "new york": "US",
    "nyc": "US", "harlem": "US", "bronx": "US", "uk": "GB", "london": "GB", "londres": "GB", "angleterre": "GB", "england": "GB", "italie": "IT",
    "italy": "IT", "italia": "IT", "milan": "IT", "milano": "IT", "bergamo": "IT", "brescia": "IT", "belgique": "BE", "belgium": "BE", "bruxelles": "BE",
    "brussels": "BE", "pays-bas": "NL", "netherlands": "NL", "amsterdam": "NL", "espagne": "ES", "spain": "ES", "barcelona": "ES", "canada": "CA",
    "europe": "FR", "burkina": "BF", "ouagadougou": "BF", "niger": "NE", "niamey": "NE", "mauritanie": "MR", "mauritania": "MR", "nouakchott": "MR",
}


def countries_in(text: str) -> list[str]:
    t = (text or "").lower()
    found = []
    for alias, code in COUNTRY_ALIASES.items():
        if re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", t) and code not in found:
            found.append(code)
    return found


def field_value(text: str, name: str) -> str:
    m = re.search(rf"^{re.escape(name)}:\s*(.*)$", text, re.M)
    return m.group(1).strip() if m else ""


class HeuristicLLM(LLM):
    """Deterministic stand-in with the same interface. Never touches the network."""

    def __init__(self, settings: Settings | None = None, recorder=None):
        super().__init__(settings, recorder)
        self._batches: dict[str, dict[str, Any]] = {}
        from ..hubs import load_hubs
        from ..taxonomy import taxonomy

        self.tax = taxonomy()
        self.hubs = load_hubs()[0]

    # ---------------------------------------------------------- dispatch

    def structured(self, stage: str, *, system: str | None, user_text: str, schema: type[T], effort: str = "medium",
                   images: list[bytes | str] | None = None, max_tokens: int = 4096) -> T:
        handler = {
            RelevanceVerdict: self._relevance, Enrichment: self._enrich, PostClassification: self._classify,
            ClusterLabel: self._cluster_label, ParsedQuery: self._parse_query, ScoreNarrative: self._narrative,
            JudgeVerdict: self._judge, QueryExpansion: self._expand, SameBusiness: self._same_business,
        }.get(schema)
        if handler is None:
            raise NotImplementedError(f"HeuristicLLM has no handler for {schema.__name__}")
        return handler(user_text)  # type: ignore[return-value]

    def submit_batch(self, stage, items, schema, *, system, effort="low", max_tokens=2048) -> str:
        bid = f"heuristic-{uuid.uuid4().hex[:12]}"
        self._batches[bid] = {it.custom_id: self.structured(stage, system=system, user_text=it.user_text, schema=schema) for it in items}
        return bid

    def batch_status(self, batch_id):
        n = len(self._batches.get(batch_id, {}))
        return "ended", {"processing": 0, "succeeded": n, "errored": 0, "canceled": 0, "expired": 0}

    def collect_batch(self, batch_id, stage, schema):
        return dict(self._batches.get(batch_id, {}))

    def run_batch(self, stage, items, schema, *, system, effort="low", max_tokens=2048, **_):
        return {it.custom_id: self.structured(stage, system=system, user_text=it.user_text, schema=schema) for it in items}

    # ---------------------------------------------------------- handlers

    def _hits(self, text: str):
        tags = re.findall(r"#\w+", text)
        return self.tax.match(text, tags)

    def _type_guess(self, text: str, hits) -> tuple[str, float]:
        t = text.lower()
        garments = sum(v for k, v in hits.items() if k.startswith("garment."))
        fabrics = sum(v for k, v in hits.items() if k.startswith("fabric."))
        if "etsy.com" in t or "afrikrea" in t:
            return "marketplace_seller", 0.8
        if hits.get("signal.wholesale"):
            # "gros et détail" sells to consumers too; treat as a retailer that also wholesales.
            return ("fabric_retailer", 0.65) if hits.get("signal.retail") else ("fabric_wholesaler", 0.7)
        if hits.get("technique.tailoring") or any(w in t for w in ("sur mesure", "made to measure", "tailleur", "couturier", "atelier")):
            return "tailor", 0.7
        if hits.get("technique.embroidery") and not garments:
            return "embroiderer", 0.6
        if fabrics and (hits.get("signal.retail") or hits.get("signal.price")) and not garments:
            return "fabric_retailer", 0.7
        if garments and (hits.get("signal.availability") or hits.get("signal.price") or hits.get("signal.order_dm")):
            return "rtw_seller", 0.6
        if fabrics:
            return "fabric_retailer", 0.5
        if garments:
            return "couture_designer", 0.5
        return "unknown", 0.3

    def _relevance(self, text: str) -> RelevanceVerdict:
        hits = self._hits(text)
        anchors = {k: v for k, v in hits.items() if k in self.tax.relevance_anchors}
        n = sum(anchors.values())
        body = re.sub(r"#\w+", "", text)
        body_hits = self.tax.match(body)
        anchor_in_body = any(k in self.tax.relevance_anchors for k in body_hits)
        btype, tconf = self._type_guess(text, hits)
        commerce = any(hits.get(s) for s in ("signal.price", "signal.order_dm", "signal.whatsapp", "signal.availability", "signal.retail", "signal.wholesale", "technique.tailoring"))
        relevant = n > 0 and (commerce or btype != "unknown")
        if not relevant:
            conf = 0.8 if n == 0 else 0.55
            reason = "No bazin vocabulary observed" if n == 0 else "Bazin terms present but no commerce or making signal"
        elif not anchor_in_body:
            conf, reason = 0.5, "Only hashtags mention bazin; no caption or bio evidence"
        else:
            conf = min(0.95, 0.6 + 0.08 * n)
            reason = f"{n} bazin mentions with commerce signals; looks like a {btype.replace('_', ' ')}"
        return RelevanceVerdict(relevant=relevant, business_type_guess=btype, confidence=conf, reason=reason, language_guess=detect_language(text))

    def _locations(self, text: str, kind: str) -> list[LocationOut]:
        """Hub cities mentioned outside shipping sentences, in order of first mention."""
        t = text.lower()
        shipping_spans = [(m.start(), m.end()) for m in re.finditer(r"(?:" + "|".join(SHIP_WORDS) + r")[^.\n]{0,80}", t)]
        found: list[tuple[int, LocationOut]] = []
        for h in self.hubs:
            for m in re.finditer(r"(?<![a-z])" + re.escape(h.city.lower()) + r"(?![a-z])", t):
                if any(a <= m.start() < b for a, b in shipping_spans):
                    continue
                found.append((m.start(), LocationOut(kind=kind, country=h.country, city=h.city, confidence=0.6, evidence=h.city)))
                break
        found.sort(key=lambda x: x[0])
        return [loc for _, loc in found][:3]

    def _enrich(self, text: str) -> Enrichment:
        from ..pipeline.identity import extract_phones, website_host
        from ..prices import COUNTRY_CURRENCY, parse_prices

        hits = self._hits(text)
        btype, tconf = self._type_guess(text, hits)
        name = field_value(text, "Name") or field_value(text, "Handle") or "Unknown vendor"
        locs = self._locations(text, "atelier" if btype in ("tailor", "couture_designer", "embroiderer") else "shop")
        country = locs[0].country if locs else None
        contacts: list[ContactOut] = []
        for p in extract_phones(text, country):
            kind = "whatsapp" if ("whatsapp" in text.lower() or "wa.me" in text.lower()) else "phone"
            contacts.append(ContactOut(kind=kind, value=p, evidence=p))
        for e in EMAIL_RE.findall(text)[:2]:
            contacts.append(ContactOut(kind="email", value=e, evidence=e))
        link = field_value(text, "Link")
        host = website_host(link)
        if host:
            contacts.append(ContactOut(kind="website", value=link, evidence=link))
        if hits.get("signal.snapchat"):
            m = re.search(r"snap(?:chat)?\s*[:👻]\s*([\w.]+)", text, re.I)
            if m:
                contacts.append(ContactOut(kind="snapchat", value=m.group(1), evidence=m.group(0)[:100]))
        if hits.get("signal.order_dm") and not contacts:
            contacts.append(ContactOut(kind="instagram_dm", value="dm", evidence="DM to order"))
        ships: list[str] = []
        for m in re.finditer(r"(?:" + "|".join(SHIP_WORDS) + r")[^.\n]{0,80}", text, re.I):
            for c in countries_in(m.group(0)):
                if c not in ships and c != country:
                    ships.append(c)
        prices = [
            PriceOut(
                price_type="fabric" if p.unit in ("metre", "yard", "piece") else "complete_outfit" if p.unit == "outfit" else "other",
                currency=p.currency, amount_min=p.amount, amount_max=p.amount, unit=p.unit,
                currency_inferred=p.currency_inferred, evidence=p.evidence[:200],
            )
            for p in parse_prices(text, COUNTRY_CURRENCY.get(country or "", None))[:6]
        ]
        offers: list[OfferOut] = []
        for cid in [k for k in hits if k.startswith("garment.")][:6]:
            gender = "women" if cid in ("garment.womens", "garment.taille_basse", "garment.ndoket", "garment.dress", "garment.bridal") else "men" if cid in ("garment.mens", "garment.agbada", "garment.babban_riga", "garment.senator", "garment.kaftan") else "unisex"
            offers.append(OfferOut(garment_concept_id=cid, fabric_concept_id="fabric.getzner" if hits.get("fabric.getzner") else "fabric.bazin.riche" if hits.get("fabric.bazin.riche") else "fabric.bazin", gender=gender,
                                   custom_or_ready="custom" if hits.get("technique.tailoring") else "ready" if hits.get("signal.availability") else "unknown", evidence=self.tax.concepts[cid].canonical_label))
        signals = CommerceSignals(
            price_shown=bool(prices), dm_to_order=bool(hits.get("signal.order_dm")), whatsapp=bool(hits.get("signal.whatsapp")) or any(c.kind == "whatsapp" for c in contacts),
            shipping_info=bool(hits.get("signal.shipping")) or bool(ships), catalogue=text.count("\n- ") >= 5,
        )
        top = [self.tax.concepts[k].canonical_label for k, _ in sorted(hits.items(), key=lambda kv: -kv[1]) if k.startswith(("garment.", "fabric."))][:3]
        where = f" in {locs[0].city}" if locs else ""
        summary = f"{name} appears to be a {btype.replace('_', ' ')}{where}" + (f" offering {', '.join(top).lower()}" if top else "") + "."
        lang = detect_language(text)
        return Enrichment(
            business_type=btype, business_type_confidence=tconf, canonical_name=name[:120], locations=locs, contact_channels=contacts,
            offers=offers, prices=prices, ships_to=ships, languages=[lang] if lang != "unknown" else [], commerce_signals=signals, summary=summary[:600],
        )

    def _classify(self, text: str) -> PostClassification:
        from ..prices import parse_prices

        hits = self._hits(text)
        concept_ids = [ConceptHit(id=k, confidence=min(0.95, 0.6 + 0.1 * v)) for k, v in hits.items() if not k.startswith("color.")]
        colors = [ColorShare(name=k.split(".")[1], share=round(1 / max(1, len([c for c in hits if c.startswith("color.")])), 2)) for k in hits if k.startswith("color.")]
        occasions = [k for k in hits if k.startswith("occasion.")]
        garments = [k for k in hits if k.startswith("garment.")]
        fabrics = [k for k in hits if k.startswith("fabric.")]
        gender = "women" if any(g in ("garment.womens", "garment.taille_basse", "garment.ndoket", "garment.dress", "garment.bridal") for g in garments) else "men" if any(g in ("garment.mens", "garment.agbada", "garment.babban_riga", "garment.senator") for g in garments) else "unknown"
        t = text.lower()
        prices = parse_prices(text)
        intent = "buy_fabric" if fabrics and not garments else "find_tailor" if hits.get("technique.tailoring") else "style_inspiration" if garments else "other"
        return PostClassification(
            concept_ids=concept_ids, colors=colors, occasion_ids=occasions, gender=gender,
            is_finished_garment=bool(garments) and not (fabrics and not garments), is_fabric_only=bool(fabrics) and not garments,
            is_fitting_or_customer=any(w in t for w in CUSTOMER_WORDS), is_embroidery_closeup=bool(hits.get("technique.embroidery")) and not garments,
            shows_price=PriceMention(currency=prices[0].currency, amount=prices[0].amount, unit=prices[0].unit) if prices else None,
            language=detect_language(text), buyer_intent=intent, visual_quality=0.5,
        )

    def _cluster_label(self, text: str) -> ClusterLabel:
        ids = re.findall(r"\b((?:garment|fabric|technique|occasion|style)\.[\w.]+)\b", text)
        top = list(dict.fromkeys(ids))[:3]
        labels = [self.tax.concepts[i].canonical_label for i in top if i in self.tax.concepts]
        markets = countries_in(text)[:3]
        label = ", ".join(labels[:2]) or "Bazin vendors"
        if markets:
            label += f" ({'/'.join(markets)})"
        return ClusterLabel(label=label[:60], description=f"Vendors mostly about {', '.join(labels) or 'bazin'}.", primary_concepts=top, typical_markets=markets)

    def _parse_query(self, text: str) -> ParsedQuery:
        from ..prices import parse_prices

        q = text.strip()
        hits = self.tax.match(q)
        ql = q.lower()
        garments = [k for k in hits if k.startswith("garment.")]
        fabrics = [k for k in hits if k.startswith("fabric.") and k != "fabric.out_of_scope"]
        occasions = [k for k in hits if k.startswith("occasion.")]
        colors = [k.split(".")[1] for k in hits if k.startswith("color.")]
        gender = "women" if re.search(r"\b(women|woman|femme|femmes|ladies|bride|mariée)\b", ql) or "garment.taille_basse" in garments or "garment.ndoket" in garments else "men" if re.search(r"\b(men|man|homme|hommes|groom)\b", ql) or "garment.agbada" in garments else "unknown"
        types: list[str] = []
        if any(w in ql for w in MAKER_WORDS):
            types += ["tailor", "couture_designer"]
        if hits.get("signal.wholesale"):
            types += ["fabric_wholesaler"]
        if any(w in ql for w in BUY_WORDS) and not types:
            types += ["fabric_retailer", "fabric_wholesaler", "brand_partner", "marketplace_seller"]
        if hits.get("technique.embroidery") and "tailor" not in types:
            types += ["embroiderer"]
        budget = None
        m = re.search(r"(?:under|below|less than|max|moins de|max\.?|jusqu'à|<)\s*(.{1,25})", ql)
        if m:
            p = parse_prices(m.group(1), None) or parse_prices(m.group(0), None)
            if p:
                budget = BudgetOut(currency=p[0].currency, max=p[0].amount)
        near = None
        for h in self.hubs:
            if re.search(r"(?<![a-z])" + re.escape(h.city.lower()) + r"(?![a-z])", ql):
                near = h.city
                break
        if near is None:
            for alias in ("nyc", "harlem", "bronx", "château rouge", "chateau rouge", "london", "milano", "milan"):
                if alias in ql:
                    near = alias
                    break
        ships_to = None
        m2 = re.search(r"(?:ship(?:s|ping)? to|deliver(?:s|y)? to|livraison(?: en| au| aux| à)?|expédition)\s+([a-zà'\- ]{2,25})", ql)
        if m2:
            cs = countries_in(m2.group(1))
            ships_to = cs[0] if cs else None
        custom = "custom" if any(w in ql for w in ("sur mesure", "made to measure", "custom", "bespoke", "maker", "tailor", "couturier")) else "ready" if any(w in ql for w in ("ready", "prêt", "pret", "in stock", "ready-made")) else "unknown"
        luxury = bool(hits.get("style.luxury"))
        return ParsedQuery(
            garment_concept_ids=garments, fabric_concept_ids=fabrics, occasion_ids=occasions, gender=gender, colors=colors,
            business_types=list(dict.fromkeys(types)), budget=budget,
            location=LocationQuery(near=near, radius_km=None, ships_to=ships_to), custom_or_ready=custom, luxury_tier=luxury,
            free_text=q, language=detect_language(q) if len(q.split()) > 3 else "unknown",
        )

    def _narrative(self, text: str) -> ScoreNarrative:
        try:
            f = json.loads(text[text.index("{") :])
        except Exception:  # noqa: BLE001
            return ScoreNarrative(reasons=[], caveats=["Feature snapshot unavailable"])
        reasons, caveats = [], []
        n = f.get("n12_relevant_observations", 0)
        if n:
            reasons.append(f"{n} bazin-related posts in the last 12 months")
        else:
            caveats.append("No recent bazin-related posts observed")
        if f.get("order_channel"):
            reasons.append("Publishes a way to order (WhatsApp, phone or DM)")
        else:
            caveats.append("No contact channel observed")
        if f.get("price_anchor"):
            reasons.append("States prices publicly")
        else:
            caveats.append("No prices observed; expect to ask")
        if f.get("city_resolved"):
            reasons.append("Location resolved to a city")
        else:
            caveats.append("Location not confirmed")
        if f.get("review_count", 0):
            reasons.append(f"{f['review_count']} reviews found")
        else:
            caveats.append("No reviews found on review sites")
        if f.get("duplicate_images", 0) >= 2:
            caveats.append("Some images also appear on other accounts")
        if f.get("scam_reports", 0):
            caveats.append("Complaint or scam reports found; verify before paying a deposit")
        return ScoreNarrative(reasons=reasons[:5], caveats=caveats[:5])

    def _judge(self, text: str) -> JudgeVerdict:
        try:
            r = json.loads(text[text.index("{") :])
        except Exception:  # noqa: BLE001
            return JudgeVerdict(business_type_ok=True, location_ok=True, contact_ok=True, score_plausible=True, issues=[], overall="accept")
        issues = []
        contact_ok = bool(r.get("contact_channels"))
        location_ok = bool(r.get("locations"))
        if not contact_ok:
            issues.append("No contact channel recorded")
        if not location_ok:
            issues.append("No location recorded")
        score = float(r.get("score") or 0)
        plausible = not (score > 0.7 and int(r.get("evidence_count") or 0) < 3)
        if not plausible:
            issues.append("High score with little evidence")
        overall = "accept" if not issues else "fix"
        return JudgeVerdict(business_type_ok=True, location_ok=location_ok, contact_ok=contact_ok, score_plausible=plausible, issues=issues, overall=overall)

    def _expand(self, text: str) -> QueryExpansion:
        return QueryExpansion(phrasings=[])

    def _same_business(self, text: str) -> SameBusiness:
        return SameBusiness(same_business=False, confidence=0.5, reason="heuristic mode never merges on names alone")


def get_llm(settings: Settings | None = None, recorder=None, spent_usd: float = 0.0) -> LLM:
    settings = settings or get_settings()
    if settings.fake_llm or not settings.anthropic_api_key:
        if not settings.fake_llm:
            log.warning("BAZIN_ANTHROPIC_API_KEY not set: using the heuristic LLM")
        return HeuristicLLM(settings, recorder)
    return LLM(settings, recorder, spent_usd)

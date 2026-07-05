"""Autonomous agent: search, fetch, summarize, risk-check; audit-instrumented."""
import os
import time
from typing import Any, Dict, List, Tuple

import requests

from app.utils.audit import make_hash


class Agent:
    """Stubbed deterministic agent with offline and live modes."""
    def __init__(self):
        self.live_mode = os.getenv("AGENT_LIVE_MODE", "false").lower() == "true"
        # Optional allowlist for safety
        self.url_allowlist = os.getenv("AGENT_URL_ALLOWLIST", "").split(",")

    def _audit_step(
        self, name: str, inputs: Dict[str, Any], outputs: Dict[str, Any], start: float
    ) -> Dict[str, Any]:
        latency_ms = int((time.perf_counter() - start) * 1000)
        out_hash = make_hash(str(outputs)) or ""
        return {
            "name": name,
            "inputs": inputs,
            "outputs": {"preview": str(outputs)[:200]},
            "latency_ms": latency_ms,
            "hash": out_hash,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def search(self, topic: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Return deterministic stub search results and audit step."""
        start = time.perf_counter()
        # Stubbed deterministic search results for offline/CI
        results = [
            {"title": f"About {topic}", "url": "https://example.com/a"},
            {"title": f"Guide to {topic}", "url": "https://example.com/b"},
        ]
        step = self._audit_step("search", {"topic": topic}, {"results": results}, start)
        return results, step

    def fetch(self, urls: List[str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Fetch content from URLs (live mode) or return stubs; respect AGENT_URL_ALLOWLIST."""
        start = time.perf_counter()
        contents: List[Dict[str, Any]] = []
        if self.live_mode:
            for u in urls[:3]:
                if self.url_allowlist and not any(
                    u.startswith(p.strip()) for p in self.url_allowlist if p.strip()
                ):
                    continue
                try:
                    r = requests.get(u, timeout=3)
                    if r.ok:
                        contents.append({"url": u, "text": r.text[:2000]})
                except Exception:
                    continue
        else:
            # Offline stub content
            for u in urls[:3]:
                contents.append({"url": u, "text": f"Sample content about {u}"})
        step = self._audit_step(
            "fetch", {"urls": urls[:3]}, {"count": len(contents)}, start
        )
        return contents, step

    def summarize(
        self, docs: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Produce stub summaries from doc texts."""
        start = time.perf_counter()
        findings = []
        for d in docs[:3]:
            text = d.get("text", "")
            summary = text[:160].strip()
            findings.append(
                {"title": d.get("url", ""), "summary": summary, "url": d.get("url")}
            )
        step = self._audit_step(
            "summarize", {"inputs": len(docs)}, {"findings": len(findings)}, start
        )
        return findings, step

    def risk_check(
        self, topic: str, findings: List[Dict[str, Any]]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if content matches DENYLIST keywords; return (flagged, audit_step)."""
        start = time.perf_counter()
        denylist = [
            s.strip().lower() for s in os.getenv("DENYLIST", "").split(",") if s.strip()
        ]
        combined = (
            topic + "\n" + "\n".join([f.get("summary", "") for f in findings])
        ).lower()
        flagged = any(term in combined for term in denylist)
        step = self._audit_step(
            "risk_check", {"denylist": denylist}, {"flagged": flagged}, start
        )
        return flagged, step

    def run(
        self, topic: str, steps: List[str]
    ) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]], bool]:
        """Execute named steps (search, fetch, summarize, risk_check); return (findings, sources, audit_steps, flagged)."""
        audit_steps: List[Dict[str, Any]] = []
        sources: List[str] = []
        findings: List[Dict[str, Any]] = []

        search_results = []
        if "search" in steps:
            search_results, step = self.search(topic)
            audit_steps.append(step)

        if "fetch" in steps:
            urls = [r["url"] for r in search_results]
            fetched, step = self.fetch(urls)
            audit_steps.append(step)
            sources = urls
        else:
            fetched = []

        if "summarize" in steps:
            findings, step = self.summarize(fetched)
            audit_steps.append(step)

        flagged = False
        if "risk_check" in steps:
            flagged, step = self.risk_check(topic, findings)
            audit_steps.append(step)

        return findings, sources, audit_steps, flagged

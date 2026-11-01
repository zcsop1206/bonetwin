"""Keyless literature search, mirroring OpenResearch's `orx discover` primitives.

OpenResearch (github.com/alphaXiv/OpenResearch) is a Rust desktop/CLI harness; its
literature layer is plain HTTPS GETs to public, token-free endpoints:
  alphaXiv  https://api.alphaxiv.org/search/v2/paper/discover/{keyword|embedding}
  OpenAlex  https://api.openalex.org/works?search=...
  PubMed    https://eutils.ncbi.nlm.nih.gov/entrez/eutils/{esearch,esummary}.fcgi
No LLM is called. Stdlib only, no install needed.

CLI:
  python openresearch_tool.py --query "..." --max-papers 8 [--sources openalex,embedding,keyword,pubmed]
Prints JSON {query, sources, papers:[{source,id,url,title,date,citations,finding}], errors, seconds}.
Every call is appended to openresearch_calls.jsonl next to this file (or $OPENRESEARCH_TOOL_LOG).
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "bonetwin-openresearch-tool/0.1 (mirrors openresearch-cli)"
MAILTO = os.environ.get("OPENALEX_MAILTO", "")  # optional polite-pool contact
OPENALEX_KEY = os.environ.get("OPENALEX_API_KEY", "")  # optional; keyless budget is ~100 searches/day
LOG = os.environ.get("OPENRESEARCH_TOOL_LOG",
                     os.path.join(os.path.dirname(os.path.abspath(__file__)), "openresearch_calls.jsonl"))


def _get(url, timeout=30):
    for attempt in range(3):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(min(int(e.headers.get("Retry-After") or attempt + 1), 5))
                continue
            raise


def _short(text, n=400):
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " ..."


def _abstract_from_index(idx):
    if not idx:
        return ""
    pos = sorted((p, w) for w, ps in idx.items() for p in ps)
    return " ".join(w for _, w in pos)


def alphaxiv(strategy, q, n):
    url = ("https://api.alphaxiv.org/search/v2/paper/discover/%s?%s"
           % (strategy, urllib.parse.urlencode({"q": q, "prioritize": "default"})))
    out = []
    for h in _get(url)[:n]:
        snip = " | ".join(s.get("snippet", "") for s in (h.get("snippets") or [])[:2])
        pid = h.get("paperId", "")
        out.append({"source": "alphaxiv-" + strategy, "id": "arxiv:" + pid,
                    "url": "https://www.alphaxiv.org/abs/" + pid, "title": h.get("title", ""),
                    "date": (h.get("publicationDate") or "")[:10], "citations": None,
                    "finding": _short(snip or h.get("abstract", ""))})
    return out


def openalex(q, n):
    params = {"search": q, "per_page": n,
              "select": "id,doi,title,publication_date,cited_by_count,abstract_inverted_index"}
    if MAILTO:
        params["mailto"] = MAILTO
    if OPENALEX_KEY:
        params["api_key"] = OPENALEX_KEY
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    out = []
    for w in _get(url).get("results", []):
        doi = w.get("doi") or ""
        out.append({"source": "openalex", "id": doi.replace("https://doi.org/", "doi:") or w.get("id"),
                    "url": doi or w.get("id"), "title": w.get("title") or "",
                    "date": w.get("publication_date") or "", "citations": w.get("cited_by_count"),
                    "finding": _short(_abstract_from_index(w.get("abstract_inverted_index")))})
    return out


def pubmed(q, n):
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    common = {"db": "pubmed", "retmode": "json", "tool": "bonetwin"}
    ids = _get(base + "esearch.fcgi?" + urllib.parse.urlencode(
        dict(common, term=q, retmax=n, sort="relevance")))["esearchresult"]["idlist"]
    if not ids:
        return []
    summ = _get(base + "esummary.fcgi?" + urllib.parse.urlencode(dict(common, id=",".join(ids))))["result"]
    return [{"source": "pubmed", "id": "pmid:" + i, "url": "https://pubmed.ncbi.nlm.nih.gov/%s/" % i,
             "title": summ[i].get("title", ""), "date": summ[i].get("pubdate", ""), "citations": None,
             "finding": "%s; %s" % (summ[i].get("fulljournalname", ""), summ[i].get("elocationid", ""))}
            for i in ids if i in summ]


SOURCES = {"openalex": openalex, "embedding": lambda q, n: alphaxiv("embedding", q, n),
           "keyword": lambda q, n: alphaxiv("keyword", q, n), "pubmed": pubmed}


def search(query, max_papers=8, sources=("openalex", "embedding")):
    t0 = time.time()
    papers, errors, seen = [], {}, set()
    for s in sources:
        try:
            for p in SOURCES[s](query, max_papers):
                key = p["title"].lower().strip()
                if key and key not in seen:
                    seen.add(key)
                    papers.append(p)
        except Exception as e:  # one source failing should not sink the call
            errors[s] = "%s: %s" % (type(e).__name__, e)
    result = {"query": query, "sources": list(sources), "papers": papers,
              "errors": errors, "seconds": round(time.time() - t0, 2)}
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "query": query,
                                "max_papers": max_papers, "sources": list(sources),
                                "n_papers": len(papers), "errors": errors,
                                "seconds": result["seconds"],
                                "ids": [p["id"] for p in papers]}) + "\n")
    except OSError:
        pass
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--query", required=True)
    ap.add_argument("--max-papers", type=int, default=8, help="per source")
    ap.add_argument("--sources", default="openalex,embedding",
                    help="comma list of: " + ",".join(SOURCES))
    a = ap.parse_args(argv)
    srcs = [s.strip() for s in a.sources.split(",") if s.strip() in SOURCES]
    out = json.dumps(search(a.query, a.max_papers, srcs), indent=1, ensure_ascii=False) + "\n"
    sys.stdout.buffer.write(out.encode("utf-8"))  # Windows consoles default to cp1252


if __name__ == "__main__":
    main()

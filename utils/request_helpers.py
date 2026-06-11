from typing import Dict
from schemas.utils import HeadersFromCtxInput


def headers_from_ctx(data: HeadersFromCtxInput) -> Dict[str, str]:
    ctx = data.ctx
    headers = {}
    try:
        if not ctx:
            return headers
        meta = getattr(ctx, "meta", None)
        if isinstance(meta, dict):
            h = meta.get("headers") or meta.get("Headers")
            if isinstance(h, dict):
                return {k: v for k,v in h.items()}
        req = getattr(ctx, "request", None)
        if req:
            h = getattr(req, "headers", None)
            if isinstance(h, dict):
                return {k: v for k, v in h.items()}
            # list of tuples
            try:
                out = {}
                for k, v in h:
                    if isinstance(k, bytes): k = k.decode("utf-8", "ignore")
                    if isinstance(v, bytes): v = v.decode("utf-8", "ignore")
                    out[k] = v
                return out
            except Exception:
                try:
                    return dict(h)
                except Exception:
                    return headers
    except Exception:
        return headers
    return headers

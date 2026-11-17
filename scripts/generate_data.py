"""Build the synthetic Lumina Streaming Co. dataset and the eval answer key."""

import _bootstrap  # noqa: F401
from _bootstrap import ROOT
from cashapp.synthetic import generate

if __name__ == "__main__":
    out = generate(ROOT)
    print(
        f"Wrote {out['deposits']} deposits (${float(out['total']):,.2f}) and {out['docs']} AR items"
    )

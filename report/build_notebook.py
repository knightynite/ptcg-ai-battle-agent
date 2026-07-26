#!/usr/bin/env python
"""Emit report/reproducibility.ipynb from the percent-format report/reproducibility.py,
then execute it top-to-bottom so the committed notebook carries printed outputs + inline
figure previews. Single source of truth = reproducibility.py.

Usage:  python report/build_notebook.py [--no-exec]
"""
import os
import sys
import nbformat
from nbformat.v4 import new_notebook, new_code_cell, new_markdown_cell

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "reproducibility.py")
OUT = os.path.join(HERE, "reproducibility.ipynb")


def split_cells(text):
    """Split a jupytext 'percent'-format script into (kind, source) cells."""
    cells, cur, kind = [], [], "code"

    def flush():
        if not cur:
            return
        src = "\n".join(cur).strip("\n")
        if src.strip() != "":
            cells.append((kind, src))

    for line in text.splitlines():
        if line.lstrip().startswith("# %%"):
            flush()
            cur = []
            kind = "markdown" if "[markdown]" in line else "code"
        else:
            if kind == "markdown":
                # strip the leading comment marker ("# " or "#")
                if line.startswith("# "):
                    cur.append(line[2:])
                elif line == "#":
                    cur.append("")
                else:
                    cur.append(line)
            else:
                cur.append(line)
    flush()
    return cells


def build():
    with open(SRC, encoding="utf-8") as fh:
        text = fh.read()
    nb = new_notebook()
    for kind, src in split_cells(text):
        nb.cells.append(new_markdown_cell(src) if kind == "markdown" else new_code_cell(src))
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    nb.metadata["language_info"] = {"name": "python"}
    nbformat.write(nb, OUT)
    print(f"wrote {OUT} with {len(nb.cells)} cells "
          f"({sum(c.cell_type=='code' for c in nb.cells)} code / "
          f"{sum(c.cell_type=='markdown' for c in nb.cells)} markdown)")
    return nb


def execute():
    from nbconvert.preprocessors import ExecutePreprocessor
    nb = nbformat.read(OUT, as_version=4)
    ep = ExecutePreprocessor(timeout=600, kernel_name="python3")
    # run with the notebook's own directory as cwd (find_repo_root() walks up to the repo)
    ep.preprocess(nb, {"metadata": {"path": HERE}})
    nbformat.write(nb, OUT)
    n_out = sum(len(c.get("outputs", [])) for c in nb.cells if c.cell_type == "code")
    n_img = sum(1 for c in nb.cells if c.cell_type == "code"
                for o in c.get("outputs", []) if "image/png" in o.get("data", {}))
    print(f"executed OK: {n_out} outputs, {n_img} inline figure previews embedded")


if __name__ == "__main__":
    build()
    if "--no-exec" not in sys.argv:
        execute()

# -*- coding: utf-8 -*-
import pptx
from pptx.opc.package import _Relationships as R
from pptx.oxml.ns import qn

print("python-pptx", pptx.__version__)
print("rel methods:", [m for m in dir(R) if "add" in m or "get_or" in m])
print("qn r:embed ->", qn("r:embed"))

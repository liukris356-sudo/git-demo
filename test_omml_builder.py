import docx
from docx.oxml import parse_xml

doc = docx.Document()
p = doc.add_paragraph()
omml = '''<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><m:r><m:t>F</m:t></m:r><m:r><m:t> = </m:t></m:r><m:sSub><m:e><m:r><m:t>K</m:t></m:r></m:e><m:sub><m:r><m:t>e</m:t></m:r></m:sub></m:sSub><m:r><m:t> · Δx</m:t></m:r></m:oMath>'''
p._p.append(parse_xml(omml))
doc.save('/home/liu/projects/git-demo-admittance/test_math.docx')
print('OMML test docx saved successfully!')

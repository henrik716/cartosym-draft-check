import sys,os
from PIL import Image
root=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ids=[int(a) for a in sys.argv[2:]]
ims=[Image.open(os.path.join(root,'out','case-%02d-1.png'%i)) for i in ids]
cols=2
w=max(i.width for i in ims);h=max(i.height for i in ims)
rows=(len(ims)+cols-1)//cols
s=Image.new('RGB',(cols*(w+6),rows*(h+6)),(255,0,255))
for k,im in enumerate(ims): s.paste(im,((k%cols)*(w+6),(k//cols)*(h+6)))
s.save(os.path.join(root,'out',sys.argv[1]))

import glob, os, sys
from PIL import Image
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fs=sorted(glob.glob(R+'/out/case-*-1.png'))
sel=[f for f in fs if any(k in f for k in sys.argv[2:])] if len(sys.argv)>2 else fs
ims=[Image.open(f) for f in sel]
cols=3; w=max(i.width for i in ims); h=max(i.height for i in ims)
rows=(len(ims)+cols-1)//cols
sh=Image.new('RGB',(cols*(w+4),rows*(h+4)),'white')
for k,i in enumerate(ims): sh.paste(i,((k%cols)*(w+4),(k//cols)*(h+4)))
sh.save(sys.argv[1])

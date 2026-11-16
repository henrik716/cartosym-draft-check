import sys,os
from PIL import Image
names=sys.argv[2:]
ims=[Image.open('out/%s.png'%n) for n in names]
W=max(i.width for i in ims); 
cols=2; rows=(len(ims)+1)//2
M=Image.new('RGB',(W*cols+10,max(i.height for i in ims)*rows+10*rows),(200,200,200))
for k,i in enumerate(ims):
    M.paste(i,((k%2)*(W+10),(k//2)*(max(j.height for j in ims)+10)))
M.save(sys.argv[1])

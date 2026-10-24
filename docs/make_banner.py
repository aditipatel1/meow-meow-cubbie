import os, sys; sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "meow-meow", "scripts"))
import card as c
from PIL import Image, ImageDraw
W,H=1600,640; c.W,c.H=W,H
img=Image.new("RGBA",(c.p(W),c.p(H)),c.RED+(255,))
d=ImageDraw.Draw(img)
for y in range(c.p(H)):
    t=y/c.p(H); col=tuple(int(c.RED_DEEP[i]+(c.RED[i]-c.RED_DEEP[i])*(1-abs(t-0.4)*1.2)) for i in range(3)); d.line([(0,y),(c.p(W),y)],fill=col)
c.cat(img, 1310, 335, 0.92)
d=ImageDraw.Draw(img)
d.text((c.p(110),c.p(120)),"T E A M   1 1 : 1 1   ·   C U B B I E   S K I L L",font=c.font("DMSans.ttf",26,"SemiBold"),fill=c.GOLD_LIGHT)
d.text((c.p(104),c.p(170)),"Meow-Meow",font=c.font("Fraunces.ttf",132,"Black"),fill=c.CREAM)
d.text((c.p(110),c.p(355)),"Your lucky study buddy in iMessage.",font=c.font("DMSans.ttf",44,"Medium"),fill=c.GOLD_LIGHT)
d.text((c.p(110),c.p(417)),"“We should study together” → a real time, a real place.",font=c.font("DMSans.ttf",34,"Regular"),fill=c.CREAM)
for (x,y,r) in [(80,560,6),(700,90,8),(860,560,5),(1520,80,7),(1500,560,9)]:
    d.ellipse([c.p(x-r),c.p(y-r),c.p(x+r),c.p(y+r)],fill=c.GOLD_LIGHT)
img.convert("RGB").resize((W,H),Image.LANCZOS).save(__import__("os").path.join(__import__("os").path.dirname(__file__), "banner.png"),optimize=True)

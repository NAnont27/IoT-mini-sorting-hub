from pathlib import Path
from html import escape
import json

OUT = Path(__file__).resolve().parent
OUT.mkdir(exist_ok=True)
C = {'signal':'#7c3aed', '5V':'#dc2626', '3V3':'#d97706', 'GND':'#17212b', 'SDA':'#ca8a04', 'SCL':'#0284c7'}

class Drawing:
    def __init__(self,w,h,title,subtitle):
        self.w,self.h=w,h
        self.items=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
          '<style>text{font-family:Tahoma,"Noto Sans Thai",sans-serif} .wire{fill:none;stroke-linejoin:round;stroke-linecap:round}</style>',
          f'<rect width="{w}" height="{h}" fill="#f6f8fb"/>']
        self.rect(25,20,w-50,112,'#173b65',rx=18)
        self.text(50,67,title,32,'white',bold=True)
        self.text(50,108,subtitle,20,'#dbeafe')
    def rect(self,x,y,w,h,fill='#fff',stroke='#cbd5e1',rx=12):
        self.items.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    def text(self,x,y,s,size=20,color='#17212b',bold=False,anchor='start'):
        self.items.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{700 if bold else 400}" text-anchor="{anchor}">{escape(str(s))}</text>')
    def line(self,points,color='signal',width=4):
        color=C.get(color,color)
        self.items.append(f'<polyline class="wire" points="'+ ' '.join(f'{x},{y}' for x,y in points)+f'" stroke="{color}" stroke-width="{width}"/>')
    def dot(self,x,y,color='signal',r=6):
        self.items.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{C.get(color,color)}"/>')
    def tag(self,x,y,s,color='GND',w=130):
        self.rect(x,y-24,w,36,C.get(color,color),C.get(color,color),6)
        self.text(x+w/2,y,s,17,'white',True,'middle')
    def resistor(self,x1,y,x2,label,color='signal'):
        self.line([(x1,y),(x1+20,y)],color)
        self.rect(x1+20,y-12,x2-x1-40,24,'#fef3c7','#8a6330',3)
        self.line([(x2-20,y),(x2,y)],color)
        self.text((x1+x2)/2,y-23,label,18,anchor='middle')
    def save(self,name):
        self.items.append('</svg>')
        p=OUT/(name+'.svg');p.write_text('\n'.join(self.items),encoding='utf-8')
        return p

# Named-pin harness. Hardware pictures are intentionally not assigned guessed header locations.
d=Drawing(1800,1670,'1 / ESP32-S3 — ผัง v2 ใช้ตัวต้านทานแทน PC817','เส้นแต่ละเส้นกำหนดจาก pin map ในโค้ด • ตำแหน่งขาในภาพเป็น breakout เชิงตรรกะ ไม่ใช่ตำแหน่งขาจริงบนบอร์ด')
d.rect(50,170,330,1240,'#163f34','#163f34',20)
d.text(215,218,'ESP32-S3-N16R8',26,'white',True,'middle')
d.text(215,250,'USB เลี้ยงบอร์ด',20,'#d1fae5',anchor='middle')
d.rect(110,282,210,75,'#b8c2c8','#eef2f7',5)
d.text(215,326,'ESP32-S3',24,'#173b65',True,'middle')
d.text(80,397,'อ่านชื่อขาบนบอร์ดจริง',19,'white')
ys={4:460,5:500,6:570,7:640,8:725,9:765,10:850,11:945,12:995,13:1045,14:1095,15:1190,16:1255,17:1320}
for pin,y in ys.items():
    d.text(100,y+7,'GPIO '+str(pin),22,'white',True)
    d.dot(380,y)

# A single module card per related sensor, connected without any wire crossings.
d.rect(650,420,1100,110)
d.text(680,451,'HX711 + Load cell',23,bold=True)
for pin,label in [(4,'DT / DOUT'),(5,'SCK / CLK')]:
    y=ys[pin];d.line([(380,y),(650,y)]);d.dot(650,y);d.text(680,y+8,label,20)
d.tag(1150,466,'VCC → 3V3','3V3',180);d.tag(1380,466,'GND → GND','GND',180)
d.text(1150,510,'Load cell: แดง E+ / ดำ E− / เขียว A+ / ขาว A−',17)

for pin,name in [(6,'MG90S — Servo ประตู'),(7,'MG996R — Servo ราง')]:
    y=ys[pin];d.rect(650,y-25,1100,60,'#fff8ed')
    d.line([(380,y),(650,y)]);d.dot(650,y);d.text(680,y+8,'ส้ม (SIG) · '+name,21,bold=True)
    d.tag(1150,y+7,'แดง → +5V EXT','5V',200);d.tag(1380,y+7,'น้ำตาล → GND','GND',220)

d.rect(650,690,1100,110)
d.text(1150,719,'VL53L0X / GY-530',23,bold=True)
for pin,label,color in [(8,'SDA','SDA'),(9,'SCL','SCL')]:
    y=ys[pin];d.line([(380,y),(650,y)],color);d.dot(650,y,color);d.text(680,y+8,label,21)
d.tag(1150,766,'VIN → 3V3','3V3',180);d.tag(1380,766,'GND → GND','GND',180)
d.text(1150,793,'XSHUT / INT ไม่ต่อ',16)

d.rect(650,825,1100,65)
d.line([(380,850),(720,850)]);d.dot(720,850)
d.line([(720,850),(780,850)]);d.dot(780,850,'GND',4)
d.line([(780,850),(810,830)],'GND',3);d.dot(820,850,'GND',4)
d.line([(820,850),(870,850)],'GND');d.tag(870,857,'GND','GND',90)
d.text(1010,858,'ปุ่ม NO • INPUT_PULLUP • ไม่ต่อ +V',21)

d.rect(650,915,1100,220,'#f0f9ff')
d.text(1160,946,'E18-D80NK ×4',23,bold=True)
for pin,name,i in [(11,'TRAY EXIT',1),(12,'A',2),(13,'B',3),(14,'HOLD',4)]:
    y=ys[pin];d.line([(380,y),(650,y)]);d.dot(650,y)
    d.text(680,y+7,f'จุด B ช่อง {i} · INPUT',20)
    d.text(1160,990+(i-1)*30,f'ตัวที่ {i}: {name}',19)
d.text(1160,1118,'R 1k / 10k / 15k ต่อช่อง — ดูภาพที่ 3',18,'#173b65',True)

for pin,name,color in [(15,'เขียว','#16a34a'),(16,'เหลือง','#eab308'),(17,'แดง','#dc2626')]:
    y=ys[pin];d.rect(650,y-33,1100,61)
    d.line([(380,y),(680,y)])
    d.resistor(680,y,820,'330Ω')
    d.line([(820,y),(900,y)])
    d.items.append(f'<circle cx="925" cy="{y}" r="18" fill="{color}" stroke="#334155" stroke-width="2"/>')
    d.line([(943,y),(1040,y)],'GND');d.tag(1040,y+7,'GND','GND',90)
    d.text(1200,y+8,f'LED {name}: anode รับจาก R / cathode ไป GND',20)

d.rect(50,1435,1700,200,'#fff7ed','#edbd80')
d.text(80,1473,'ไฟเลี้ยงและจุดร่วม — ชื่อ NET เดียวกันภายในภาพนี้คือจุดที่ต่อถึงกัน',25,bold=True)
d.text(80,1515,'+5V EXT = Adapter 5V 5A → แดง Servo ทั้งสอง + น้ำตาล E18 ทั้งสี่ (ต่อขนาน)',21,C['5V'])
d.text(80,1552,'GND = ลบ Adapter + น้ำตาล Servo + น้ำเงิน E18 + ESP32 GND + Pi pin6',21,C['GND'])
d.text(80,1589,'3V3 ของ ESP32 → HX711 / ToF • IR ใช้ R จากไฟ 5V • ไม่ผูก 3V3 หรือ +5V ต่างแหล่งเข้าด้วยกัน',19,C['3V3'])
d.text(80,1620,'ถอดสายพ่วง GPIO6–GPIO7 เดิมออก • ภาพนี้ไม่ใช่ผลจำลอง Tinkercad • ถอดไฟก่อนเปลี่ยนสาย',18,'#9f1239',True)
esp=d.save('01_esp32_wiring_v2')

# Pi: isolated terminal nodes + horizontal buses; all connection dots are exact.
d=Drawing(1800,1310,'2 / Raspberry Pi 5 — ผัง v2 / AS5600 + BH1750','เลขฝั่ง Pi เป็นตำแหน่งขาจริง (PHYSICAL PIN) • ใช้ไฟเซนเซอร์ 3.3V • สายสัญญาณต่อขนาน')
d.rect(50,180,460,900,'#176247','#176247',20)
d.text(280,235,'Raspberry Pi 5',30,'white',True,'middle')
d.rect(130,280,300,120,'#bbc3c8','#e5e7eb',8);d.text(280,350,'Pi 5',35,'#173b65',True,'middle')
d.text(85,450,'ขาที่นำออกมาใช้:',22,'white',True)
pirows=[(1,'3.3V','3V3',520),(6,'GND','GND',620),(3,'SDA / GPIO2','SDA',720),(5,'SCL / GPIO3','SCL',820)]
busx={'3V3':700,'GND':800,'SDA':900,'SCL':1000}
for pin,label,key,y in pirows:
    d.text(80,y+8,f'Pin {pin} · {label}',23,'white',True)
    d.dot(510,y,key);d.line([(510,y),(busx[key],y),(busx[key],180)],key)
    d.dot(busx[key],y,key)
    d.tag(busx[key]-40,180,key,key,80)
d.text(85,920,'Pin2 / Pin4 (5V): ไม่ใช้',21,'#fee2e2',True)
d.text(85,965,'USB-C PSU ของ Pi',21,'white')
d.text(85,1005,'Wi-Fi MQTT ↔ ESP32',21,'#dbeafe',True)
for top,name,address in [(220,'BH1750 / GY-30','0x23'),(650,'AS5600','0x36')]:
    d.rect(1120,top,620,350)
    d.text(1160,top+45,name,29,bold=True)
    d.text(1560,top+45,address,25,'#173b65',True)
    for i,(key,label) in enumerate([('3V3','VCC'),('GND','GND'),('SDA','SDA'),('SCL','SCL')]):
        y=top+90+i*55
        # Extend buses to lower sensor; each rail has a separate x coordinate.
        d.line([(busx[key],180),(busx[key],y),(1120,y)],key)
        d.dot(busx[key],y,key);d.dot(1120,y,key)
        d.text(1160,y+8,label,22,bold=True)
    if name.startswith('BH'):
        d.text(1160,top+325,'ADDR → GND',21,bold=True)
    else:
        d.text(1160,top+325,'OUT / DIR / PGO: ไม่ต่อ',20)

d.rect(550,1040,1190,90,'#f0f9ff')
d.text(580,1077,'AS5600: แม่เหล็ก Diametric ตรงกลางเหนือชิป เริ่มห่าง 1–2 มม.',22,bold=True)
d.text(580,1110,'บอร์ดอยู่นิ่ง หมุนแม่เหล็กรอบแกนของมัน • i2cdetect ควรพบ 23 และ 36',20)
d.rect(50,1155,1690,120,'#fff7ed','#edbd80')
d.text(80,1192,'GND ของ Pi pin6 → ต่อร่วม ESP32 GND / ลบ Adapter',23,bold=True)
d.text(80,1230,'ห้ามนำ +5V จาก Adapter Servo มาเชื่อมขาไฟ Pi • Camera Module 3 ใช้สาย CSI 15→22 pin แยก (ฝั่ง AI)',20,'#9f1239')
d.text(80,1263,'ภาพเป็นผัง breakout เชิงตรรกะ ไม่ใช่ตำแหน่งขาจริงบนตัวบอร์ด • ถอดไฟก่อนต่อสาย',18)
pi=d.save('02_pi_wiring_v2')

d=Drawing(1600,1220,'3 / E18-D80NK — วงจรตัวต้านทาน v2 / ไม่ใช้ PC817','1 ช่อง = R1 1kΩ + R2 10kΩ + R3 15kΩ • ทำซ้ำสี่ชุด • GPIO ต้องต่อจุด B เท่านั้น')
d.rect(40,170,1520,680)
d.tag(80,337,'EXT +5V','5V',160)
d.line([(240,330),(320,330)],'5V')
d.resistor(320,330,500,'R1 = 1kΩ','5V')
d.line([(500,330),(630,330)],'5V')
d.dot(630,330,'5V')
d.text(630,265,'จุด A · OUT เซนเซอร์',23,bold=True,anchor='middle')
d.line([(630,330),(800,330)],'GND')
d.resistor(800,330,970,'R2 = 10kΩ','GND')
d.line([(970,330),(1100,330)],'signal')
d.dot(1100,330)
d.text(1100,265,'จุด B · เข้า GPIO',23,bold=True,anchor='middle')
d.line([(1100,330),(1340,330)],'signal')
d.tag(1340,337,'GPIO11–14','signal',170)
d.line([(1100,330),(1100,420)],'GND')
d.rect(1086,420,28,100,'#fef3c7','#8a6330',3)
d.text(1150,477,'R3 = 15kΩ',22,bold=True)
d.line([(1100,520),(1100,626)],'GND')
d.tag(1040,650,'GND','GND',120)
d.text(970,710,'ไม่ต่อจุด A เข้า GPIO ตรง',23,'#9f1239',True)
d.text(970,752,'โค้ด IR: pinMode(pin, INPUT)',21,'#173b65',True)
d.text(970,791,'LOW = พบวัตถุ / HIGH = ว่าง',20)

d.rect(80,540,340,230,'#fff8dc','#ca8a04')
d.text(110,580,'E18-D80NK · NPN NO',22,bold=True)
d.text(110,615,'น้ำตาล · VCC',21)
d.text(110,676,'ดำ · OUT',21)
d.text(110,740,'น้ำเงิน · GND',21)
d.dot(420,595,'5V');d.line([(420,595),(460,595)],'5V')
d.tag(460,602,'EXT +5V','5V',130)
d.dot(420,660,'GND');d.line([(420,660),(630,660),(630,330)],'GND')
d.dot(420,725,'GND');d.line([(420,725),(460,725)],'GND')
d.tag(460,732,'GND','GND',130)

d.rect(40,880,1520,295)
d.text(80,924,'ทำซ้ำวงจรข้างบน แยกจุด A/B ของแต่ละเซนเซอร์',25,bold=True)
for i,(name,pin) in enumerate([('TRAY EXIT',11),('A',12),('B',13),('HOLD',14)]):
    x=80+i*375
    d.text(x,977,f'E18 {i+1}: {name}',22,bold=True)
    d.text(x,1017,f'จุด B → GPIO{pin}',21)
    d.text(x,1054,'1kΩ ×1 / 10kΩ ×1 / 15kΩ ×1',17)
d.text(80,1100,'รวม IR: 1kΩ ×4 + 10kΩ ×4 + 15kΩ ×4   •   LED: 330Ω ×3   →   รวม R 15 ตัว (¼W)',20,bold=True)
d.text(80,1141,'ไฟ regulated 5V เท่านั้น • วัดจุด B ก่อนต่อ GPIO: HIGH ราว 2.9–3.0V / LOW ใกล้ 0V • เปิด ESP32 ก่อน Adapter',18,'#9f1239')
ir=d.save('03_ir_resistor_v2')

(OUT/'render_manifest.json').write_text(json.dumps([{'svg':p.name,'png':p.with_suffix('.png').name} for p in (esp,pi,ir)],indent=2),encoding='utf-8')
print('\n'.join(str(p) for p in (esp,pi,ir)))

"""Generate the isometric physical-layout SVG (#phys) for index.html.

Usage: python assets/diagrams/physical_layout.py index.html
Rewrites the <svg id="phys"> block in place; colours come from the iso-* CSS in index.html.
Edit the scene section below (devices, labels, links) and run again.
"""
import math
import sys

C, S = math.cos(math.radians(30)), 0.5
out = []


def P(cx, cy, x, y, z):
    return (cx + (x - y) * C, cy + (x + y) * S - z)


def poly(pts, cls, extra=''):
    d = ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)
    out.append(f'<polygon class="{cls}" points="{d}"{extra}/>')


def box(cx, cy, x0, y0, z0, w, d, h, top='iso-t', left='iso-l', right='iso-r'):
    x1, y1, z1 = x0 + w, y0 + d, z0 + h
    p = lambda x, y, z: P(cx, cy, x, y, z)
    poly([p(x1, y0, z0), p(x1, y1, z0), p(x1, y1, z1), p(x1, y0, z1)], right)
    poly([p(x0, y1, z0), p(x1, y1, z0), p(x1, y1, z1), p(x0, y1, z1)], left)
    poly([p(x0, y0, z1), p(x1, y0, z1), p(x1, y1, z1), p(x0, y1, z1)], top)


def leds(cx, cy, x0, y1, z, xs, cls='iso-led'):
    for u in xs:
        x, y = P(cx, cy, x0 + u, y1, z)
        out.append(f'<circle class="{cls}" cx="{x:.1f}" cy="{y:.1f}" r="2.6"/>')


def floor(cx, cy, a):
    poly([P(cx, cy, -a, -a, 0), P(cx, cy, a, -a, 0), P(cx, cy, a, a, 0), P(cx, cy, -a, a, 0)], 'iso-floor')


def label(cx, y, name, sub=None, sub2=None):
    out.append(f'<text class="iso-name" x="{cx}" y="{y}" text-anchor="middle">{name}</text>')
    if sub:
        out.append(f'<text class="iso-sub" x="{cx}" y="{y + 18}" text-anchor="middle">{sub}</text>')
    if sub2:
        out.append(f'<text class="iso-sub" x="{cx}" y="{y + 34}" text-anchor="middle">{sub2}</text>')


def tag(x, y, text, cls):
    w = 9 + len(text) * 7.2
    out.append(f'<rect class="iso-tag {cls}" x="{x - w / 2:.1f}" y="{y - 10}" width="{w:.1f}" height="20" rx="10"/>'
               f'<text class="iso-tagt" x="{x}" y="{y + 4}" text-anchor="middle">{text}</text>')


# ------------------------------------------------------------------ icons (cx, cy = floor centre)
def server_stack(cx, cy, n=3, accent=None):
    floor(cx, cy, 46)
    for i in range(n):
        box(cx, cy, -32, -24, 6 + i * 18, 64, 48, 14)
        leds(cx, cy, -32, 24, 6 + i * 18 + 7, (10, 18), 'iso-led' if not accent else 'iso-led ' + accent)


def tower(cx, cy):
    floor(cx, cy, 40)
    box(cx, cy, -16, -28, 4, 32, 56, 92)
    for k in range(3):
        z = 70 - k * 22
        a, b = P(cx, cy, 16, -18, z), P(cx, cy, 16, 18, z)
        out.append(f'<line class="iso-slot" x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}"/>')
        x, y = P(cx, cy, 16, -22, z - 4)
        out.append(f'<circle class="iso-led" cx="{x:.1f}" cy="{y:.1f}" r="2.6"/>')


def laptop(cx, cy):
    floor(cx, cy, 44)
    box(cx, cy, -34, -24, 2, 68, 48, 5)
    p = lambda x, y, z: P(cx, cy, x, y, z)
    poly([p(-34, -24, 7), p(34, -24, 7), p(34, -34, 56), p(-34, -34, 56)], 'iso-screen')
    for k, u in enumerate((0.75, 0.6, 0.45)):
        a, b = p(-26, -24 - 10 * u, 7 + 49 * u), p(-26 + 40 - k * 8, -24 - 10 * u, 7 + 49 * u)
        out.append(f'<line class="iso-code" x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}"/>')


def monitor(cx, cy):
    box(cx, cy, -8, -8, 0, 16, 16, 22)
    p = lambda x, y, z: P(cx, cy, x, y, z)
    poly([p(-36, -2, 22), p(36, -2, 22), p(36, -2, 72), p(-36, -2, 72)], 'iso-screen')
    for k, u in enumerate((0.7, 0.5, 0.3)):
        a, b = p(-28, -2, 22 + 50 * u), p(-28 + 44 - k * 10, -2, 22 + 50 * u)
        out.append(f'<line class="iso-code" x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}"/>')


def ct_scanner(cx, cy):
    floor(cx, cy, 70)
    box(cx, cy, 6, -12, 0, 92, 24, 16)          # table base
    box(cx, cy, 6, -14, 16, 96, 28, 5, top='iso-t iso-soft')  # table top
    box(cx, cy, -30, -46, 0, 26, 92, 88)          # gantry
    pts = [P(cx, cy, -4, 28 * math.cos(t), 44 + 28 * math.sin(t)) for t in [i * math.pi / 14 for i in range(28)]]
    poly(pts, 'iso-bore')


def switch(cx, cy, w=120):
    floor(cx, cy, 58)
    box(cx, cy, -w / 2, -18, 6, w, 36, 13)
    leds(cx, cy, -w / 2, 18, 12.5, [10 + 9 * k for k in range(int((w - 20) / 9))], 'iso-port')


def appliance_pair(cx, cy, cls_led='iso-led', antennas=False):
    floor(cx, cy, 46)
    for i in range(2):
        box(cx, cy, -34, -22, 4 + i * 17, 68, 44, 12)
        leds(cx, cy, -34, 22, 4 + i * 17 + 6, (10, 17, 24), cls_led)
    if antennas:
        for x in (-26, 22):
            a, b = P(cx, cy, x, -20, 33), P(cx, cy, x, -20, 62)
            out.append(f'<line class="iso-ant" x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}"/>')


def firewall(cx, cy):
    floor(cx, cy, 46)
    for i in range(2):
        box(cx, cy, -34, -22, 4 + i * 17, 68, 44, 12, left='iso-l iso-amber')
    for z in (10, 27):
        a, b = P(cx, cy, -30, 22, z), P(cx, cy, 30, 22, z)
        out.append(f'<line class="iso-brick" x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}"/>')


def rack(cx, cy, units):
    """units: list of role classes from top to bottom"""
    floor(cx, cy, 52)
    box(cx, cy, -26, -26, 0, 52, 52, 190)
    p = lambda x, y, z: P(cx, cy, x, y, z)
    z = 176
    for role in units:
        poly([p(-21, 26, z - 15), p(21, 26, z - 15), p(21, 26, z), p(-21, 26, z)], f'iso-unit {role}')
        x, y = p(-15, 26, z - 7.5)
        out.append(f'<circle class="iso-led" cx="{x:.1f}" cy="{y:.1f}" r="2.2"/>')
        z -= 19


def cylinder(cx, cy, r=26, h=46, cls='iso-cyl'):
    rx, ry = r * 1.22, r * 0.62
    floor(cx, cy, r + 10)
    top = cy - h
    out.append(f'<path class="{cls}" d="M{cx - rx:.1f} {top:.1f} L{cx - rx:.1f} {cy:.1f} A{rx:.1f} {ry:.1f} 0 0 0 {cx + rx:.1f} {cy:.1f} '
               f'L{cx + rx:.1f} {top:.1f} A{rx:.1f} {ry:.1f} 0 0 1 {cx - rx:.1f} {top:.1f} Z"/>')
    out.append(f'<ellipse class="{cls} iso-cyltop" cx="{cx}" cy="{top:.1f}" rx="{rx:.1f}" ry="{ry:.1f}"/>')


def cloud(cx, cy, globe=True):
    out.append(f'<ellipse class="iso-floor" cx="{cx}" cy="{cy + 34}" rx="78" ry="20"/>')
    out.append(f'<path class="iso-cloud" transform="translate({cx},{cy})" d="M-62 28 C-86 28 -88 -4 -64 -8 C-62 -34 -28 -42 -12 -24 '
               f'C0 -48 44 -44 46 -14 C72 -14 80 26 52 28 Z"/>')
    if globe:
        out.append(f'<g class="iso-globe" transform="translate({cx},{cy + 4})"><circle r="15"/><ellipse rx="6.5" ry="15"/>'
                   f'<line x1="-15" y1="0" x2="15" y2="0"/></g>')


def line(pts, cls='iso-link'):
    d = 'M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in pts)
    out.append(f'<path class="{cls}" d="{d}"/>')


def zone(x, y, w, h, title, sub=None, cls='iso-zone'):
    out.append(f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="18"/>')
    out.append(f'<text class="iso-zonet" x="{x + 18}" y="{y + 28}">{title}</text>')
    if sub:
        out.append(f'<text class="iso-zones" x="{x + 18}" y="{y + 46}">{sub}</text>')


def unit_list(x, y, items):
    yy = y
    for role, name, subs in items:
        out.append(f'<rect class="iso-key {role}" x="{x}" y="{yy - 11}" width="12" height="12" rx="3"/>')
        out.append(f'<text class="iso-li" x="{x + 20}" y="{yy}">{name}</text>')
        for k, sub in enumerate(subs):
            out.append(f'<text class="iso-lis" x="{x + 20}" y="{yy + 16 + 15 * k}">{sub}</text>')
        yy += 26 + 15 * len(subs)


# ------------------------------------------------------------------ scene
W, H = 1840, 1230
out.append(f'<rect class="iso-bg" x="0" y="0" width="{W}" height="{H}"/>')
out.append('<text class="iso-h1" x="24" y="40">Physical layout · Scenario 1</text>')
out.append('<text class="iso-h2" x="24" y="64">One hospital server room with two racks on separate UPS feeds · inference GPU in the hospital · research server on the HCMUT lab GPU · cloud for backup only</text>')

zone(20, 90, 1290, 1120, 'HOSPITAL · MAIN SITE')
zone(40, 130, 1250, 340, 'CLINICAL AND RESEARCH ROOMS', 'connected through the building network', 'iso-zone2')
zone(40, 610, 1250, 580, 'SERVER ROOM', 'racks A and B on separate UPS feeds (battery-backed power) · network rack on both', 'iso-zone2')
zone(1340, 90, 480, 380, 'CLOUD PROVIDER', 'storage only, no compute')
zone(1340, 740, 480, 470, 'HCMUT LAB', 'run by the AI team', 'iso-zone iso-zlab')

ct_scanner(190, 352)
label(190, 428, 'CT / MRI scanner', 'CT room · VLAN 10')
monitor(450, 340); monitor(510, 372)
label(480, 428, 'Radiologist workstations', '3D Slicer + ICH Triage · VLAN 20')
laptop(780, 352)
label(780, 428, 'Annotator laptops', 'Slicer + MONAILabel · VLAN 40')
tower(1090, 340)
label(1090, 428, 'HIS / RIS', 'existing · HL7 / FHIR')

switch(640, 548)
label(640, 594, 'Core switch pair', 'VLAN 10–80 · deny by default')
for x in (190, 480, 780, 1090):
    line([(x, 452), (x, 486), (640, 486), (640, 514)])

rack(150, 1010, ['r-gpu', 'r-app', 'r-db', 'r-st', 'r-st', 'r-free', 'r-ups'])
label(150, 1060, 'Rack A', 'UPS feed A')
unit_list(225, 730, [
    ('r-gpu', 'Inference GPU server', ['MONAI · hemorrhage_approved · VLAN 30']),
    ('r-app', 'App host A (VMs)', ['dcm4chee 1 · Orthanc 1 + AI worker', 'Keycloak · OpenLDAP 1 · etcd 1']),
    ('r-db', 'PostgreSQL primary', ['Patroni · PACS index, AI results']),
    ('r-st', 'Storage nodes 1–2', ['SeaweedFS · copy in rack B']),
    ('r-ups', 'UPS A', ['battery-backed power']),
])
rack(560, 1010, ['r-res', 'r-app', 'r-db', 'r-st', 'r-st', 'r-bak', 'r-ups'])
label(560, 1060, 'Rack B', 'UPS feed B')
unit_list(635, 730, [
    ('r-res', 'Research Orthanc host', ['label store + model registry · VLAN 40']),
    ('r-app', 'App host B (VMs)', ['dcm4chee 2 · Orthanc 2 + AI worker', 'OpenLDAP 2 · etcd 2']),
    ('r-db', 'PostgreSQL standby', ['streaming replica · failover']),
    ('r-st', 'Storage nodes 3–4', ['SeaweedFS · copy in rack A']),
    ('r-bak', 'Backup gateway', ['pgBackRest · rclone → cloud']),
    ('r-ups', 'UPS B', ['battery-backed power']),
])
appliance_pair(1010, 770)
label(1010, 820, 'Load balancer pair', 'VIPs: PACS, Orthanc, PG')
firewall(1190, 770)
label(1190, 820, 'Egress firewall pair', '443 out · IPsec VPN')
switch(1010, 1000, w=96)
label(1010, 1045, 'Storage switch', 'VLAN 80')
tower(1190, 1000)
label(1190, 1090, 'Witness host', 'etcd 3 · SeaweedFS master')
line([(640, 612), (640, 660), (150, 660), (150, 810)])
line([(640, 660), (560, 660), (560, 810)])
line([(640, 660), (1010, 660), (1010, 726)])
line([(1010, 660), (1190, 660), (1190, 726)])
line([(1010, 870), (1010, 970)])

cloud(1560, 600)
label(1560, 668, 'Internet', 'ISP 1 + ISP 2')
line([(1240, 770), (1300, 770), (1300, 600), (1480, 600)], 'iso-link iso-lout')
cylinder(1430, 320)
label(1430, 370, 'DICOM tiers', 'Standard → IA → Archive', '10 years · Object Lock')
cylinder(1590, 320)
label(1590, 370, 'Research copy', 'labels, frozen datasets')
cylinder(1740, 320, r=22)
label(1740, 370, 'PG backups', 'WAL + base · 35 d')
out.append('<text class="iso-sub" x="1360" y="450">Encrypted with hospital-held keys (KMS).</text>')
line([(1560, 562), (1560, 470)], 'iso-link iso-lout')
server_stack(1500, 980, n=4, accent='iso-led-gpu')
tag(1500, 862, 'GPU', 'iso-tag-gpu')
label(1500, 1040, 'Research server', 'MONAI · hemorrhage_dev', 'drafts · active learning · training')
server_stack(1710, 980, n=3)
label(1710, 1040, 'Staging (4 servers)', 'PACS · Gateway · DB · Storage', 'test data only')
line([(1625, 620), (1680, 620), (1680, 740)], 'iso-link iso-lvpn')
out.append('<text class="iso-vpn" x="1360" y="800">site-to-site VPN: the lab reaches VLAN 40 only</text>')
out.append('<text class="iso-sub" x="1360" y="1160">De-identified data only; cache cleared nightly.</text>')
out.append('<text class="iso-sub" x="1360" y="1178">Label store, registry and approval stay in the hospital.</text>')

ly = 1150
for k, (role, txt) in enumerate((('r-gpu', 'AI inference'), ('r-res', 'AI research'), ('r-app', 'App host (VMs)'),
                                 ('r-db', 'Database'), ('r-st', 'Storage'), ('r-bak', 'Backup and egress'), ('r-ups', 'Power'))):
    x = 60 + k * 170
    out.append(f'<rect class="iso-key {role}" x="{x}" y="{ly + 30}" width="12" height="12" rx="3"/><text class="iso-lis" x="{x + 18}" y="{ly + 41}">{txt}</text>')

svg = (f'<svg id="phys" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-labelledby="pttl pdsc">\n'
       '<title id="pttl">Physical layout, Scenario 1</title>\n'
       '<desc id="pdsc">Isometric drawing of where each part runs. In the hospital, the CT room, reading room, annotator laptops and HIS/RIS connect to a core switch pair. '
       'The server room has rack A (inference GPU server, app host A, PostgreSQL primary, storage nodes 1 and 2, UPS A) and rack B (research Orthanc host with the label store and model registry, '
       'app host B, PostgreSQL standby, storage nodes 3 and 4, backup gateway, UPS B), plus a load balancer pair, an egress firewall pair, a storage switch and a witness host. '
       'The firewall reaches the internet over two providers; from there the cloud provider holds the DICOM tiers, the research copy and the database backups, '
       'and the HCMUT lab runs the research server on a GPU and the four staging servers. The lab reaches only VLAN 40 over a site-to-site VPN.</desc>\n'
       + '\n'.join(out) + '\n</svg>')

if __name__ == '__main__':
    page = sys.argv[1]
    raw = open(page, encoding='utf-8', newline='').read()
    crlf = chr(13) + chr(10)
    text = raw.replace(crlf, chr(10))
    i = text.index('<svg id="phys"')
    j = text.index('</svg>', i) + len('</svg>')
    text = text[:i] + svg + text[j:]
    if crlf in raw:
        text = text.replace(chr(10), crlf)
    open(page, 'w', encoding='utf-8', newline='').write(text)
    print('updated', page)

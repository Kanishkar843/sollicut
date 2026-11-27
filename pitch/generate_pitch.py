"""Selectable-text deck. Run from the repository root with Python 3.11."""
from pathlib import Path
from html import escape

from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "pitch/SolliCut_Pitch.pdf"
W, H = 960, 540
GREEN, INK, MUTED, LIME = "#203b2c", "#23372e", "#66776a", "#d9f29e"


def build():
    OUTPUT.parent.mkdir(exist_ok=True)
    c = canvas.Canvas(str(OUTPUT), pagesize=(W, H))
    c.setTitle("SolliCut | Speak it. Cut it. Sell it.")
    c.setAuthor("SolliCut project")
    content = []

    def box(x, y, width, height, color, radius=12):
        c.setFillColor(HexColor(color)); c.roundRect(x, y, width, height, radius, fill=1, stroke=0)

    def text(value, x, y, width=840, size=18, color=INK, bold=False):
        style = ParagraphStyle("body", fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size, leading=size*1.42, textColor=HexColor(color))
        paragraph = Paragraph(value, style)
        _, height = paragraph.wrap(width, 500)
        paragraph.drawOn(c, x, y-height)
        content.append(value.replace("<br/>", "\n"))
        return height

    def page(number, eyebrow, title):
        c.setFillColor(HexColor("#f7f9f3")); c.rect(0, 0, W, H, fill=1, stroke=0)
        text("SolliCut", 48, 507, size=16, bold=True)
        text(eyebrow.upper(), 48, 448, size=11, color=MUTED, bold=True)
        text(title, 48, 420, size=34, bold=True)
        c.setStrokeColor(HexColor("#dce5d5")); c.line(48, 45, 912, 45)
        text("Speak it. Cut it. Sell it.  |  Round 2 prototype", 48, 31, size=10, color=MUTED)
        text(f"{number:02d} / 07", 856, 31, 70, size=10, color=MUTED)

    page(1, "Livelihoods and small business", "Your products. Your words.")
    box(48, 124, 565, 225, GREEN)
    text("Speak it.<br/>Cut it. Sell it.", 76, 321, 500, 48, "#f1f6e9", True)
    text("Voice-first promotional video creation<br/>for India's micro-businesses.", 650, 325, 260, 20)
    text("Tamil / Tanglish / English<br/><br/>Real photos. Local speech recognition.<br/>Actual downloadable MP4.", 650, 190, 260, 15, MUTED)
    c.showPage()

    page(2, "Problem and solution", "Creative intent should not need a timeline.")
    box(48, 134, 414, 218, "#eaf0e4")
    text("The problem", 72, 327, 360, 20, bold=True)
    text("A small seller has product photos and clips. Making a reel still asks them to learn complex editing controls and keyframes.", 72, 281, 355, 19)
    box(486, 134, 426, 218, GREEN)
    text("The solution", 510, 327, 375, 20, "#d9f29e", True)
    text("Say the creative instruction in a comfortable language. SolliCut maps it to validated edits and renders the seller's own media.", 510, 281, 360, 19, "#ffffff")
    text("Programmatic photo & video reel creation. Keyless core editing; optional Gemini Omni ad generation only if configured.", 48, 101, 855, 14, MUTED)
    c.showPage()

    page(3, "Users and workflow", "A small seller's next offer reel.")
    text("Initial users: boutiques, florists, beauty studios, local retailers, home kitchens and bakeries in Tamil Nadu.", 48, 352, 850, 18, MUTED)
    box(48, 193, 864, 99, GREEN)
    text('"Indha photos ellathayum use panni oru 15 seconds Instagram reel create pannu. Smooth zoom effects podu. Background music add pannu. Last la 20 percent offer nu text podu."', 70, 272, 820, 18, "#ffffff")
    labels = ["Upload 1-5 clips", "Speak your idea", "Preview & timeline", "Say another edit", "Undo / download"]
    for index, label in enumerate(labels):
        box(48+index*175, 114, 164, 48, "#e5eddd", 8)
        text(label, 59+index*175, 146, 145, 12, bold=True)
    text("Follow-up: change the offer to 25 percent, reduce music, trim or reorder clips.", 48, 87, 860, 14, MUTED)
    c.showPage()

    page(4, "Market context", "A large universe. A deliberately small pilot.")
    universe = 6_051_034
    serviceable = round(universe * .05)
    reachable = round(universe * .05 * .2)
    text("6.05 million", 48, 353, 420, 44, GREEN, True)
    text("Tamil Nadu enterprise registrations<br/>including informal micro enterprises on UAP", 48, 285, 405, 17, MUTED)
    box(505, 167, 407, 184, GREEN)
    text("ILLUSTRATIVE SCENARIOS", 529, 327, 350, 11, LIME, True)
    text(f"5% with recurring reel needs: ~{serviceable:,}<br/><br/>20% of that group reachable: ~{reachable:,}", 529, 292, 355, 20, "#ffffff")
    text("Registration counts are upper-bound context, not customer counts. The 5% and 20% rates are planning assumptions, not measured demand.", 48, 183, 410, 15)
    text("Pilot goal: 1,000 active businesses. Start by observing 20-30 sellers.", 48, 99, 850, 17, bold=True)
    text("Source: Ministry of MSME Annual Report 2025-26, Table 3.2, printed p.35; as of 31 Jan 2026. Accessed 27 Nov 2026.", 48, 69, 860, 9, MUTED)
    c.showPage()

    page(5, "Technology and dependencies", "Local by default. Replaceable where it matters.")
    text("MediaRecorder  /  faster-whisper + CTranslate2 CPU INT8  /  deterministic parser<br/>FastAPI  /  FFmpeg  /  Pillow + libraqm + Noto Sans Tamil  /  React  /  Docker Compose", 48, 354, 860, 17)
    rows = [
        ("API prices rise or cloud services fail", "Core speech and rendering need no hosted AI API."),
        ("Tamil / Tanglish recognition varies", "Benchmark real voices; ask for clarification. Replace the speech engine if needed."),
        ("CPU processing takes too long", "Short commands, 720p reels and one render at a time; measure on actual hardware."),
        ("Alternative engine needed", "Evaluate AI4Bharat / Bodhan; review model terms. Hosted BHASHINI needs credentials."),
    ]
    for i, (risk, response) in enumerate(rows):
        y=258-i*47
        box(48,y-28,864,43,"#eaf0e4" if i%2==0 else "#f0f4eb",5)
        text(escape(risk),60,y+5,275,13,bold=True)
        text(escape(response),350,y+5,545,12)
    text("No accuracy or real-time performance claim is made without a project-specific benchmark.",48,65,850,11,MUTED)
    c.showPage()

    page(6, "Launch and growth", "Learn the language of the first 30 sellers.")
    columns=[("OBSERVE", "20-30 Tamil-speaking home businesses", "Recruit through personal outreach and local seller / creator communities. Watch natural commands and record consented failures."),
             ("REFINE", "Turn repeated needs into reliable edits", "Measure intent success, repeat use and time to a usable reel. Add bakery, boutique and beauty templates after the core is reliable."),
             ("EXPAND", "Reach 1,000 active pilot businesses", "Approach seller networks, entrepreneurship cells and digital-marketing trainers. These are planned channels, not claimed partnerships.")]
    for i,(label,title,body) in enumerate(columns):
        x=48+i*294
        box(x,136,276,222,GREEN if i==0 else "#eaf0e4")
        color="#ffffff" if i==0 else INK
        text(label,x+19,335,235,11,LIME if i==0 else MUTED,True)
        text(title,x+19,305,235,19,color,True)
        text(body,x+19,234,235,13,color)
    text("Growth hypothesis: shared reels bring other sellers. Test an optional Made with SolliCut end card later. Expand languages only after demand and ASR validation.",48,113,855,14,MUTED)
    c.showPage()

    page(7, "Round 2 prototype", "One honest end-to-end demonstration.")
    box(48,136,420,220,GREEN)
    text("Verified in automated tests",72,331,370,20,LIME,True)
    text("Multilingual voice command parsing<br/>Photo and MP4/MOV/WebM clip rendering<br/>Clip trim, reorder, music & audio mixing<br/>Tamil overlay shaping with libraqm<br/>Studio timeline, undo & keyless setup",72,286,365,17,"#ffffff")
    text("Still needs human acceptance",510,339,385,20,bold=True)
    text("Real browser microphone + participant voice<br/>Tanglish intent success benchmark<br/>Independent person's fresh clone<br/>Public/unlisted demo under 3 minutes",510,296,380,16,MUTED)
    text("Optional Gemini Omni 1.2 Flash ad tab shows Key not set without credentials; live cloud generation is untested without a key.",510,177,380,14)
    text("Submission cutoff supplied by participant: 30 Nov 2026, 11:59 pm IST. VERIFY in the authenticated dashboard; the public page currently differs.",48,100,860,12,"#85551f")
    text("github.com/Kanishkar843/sollicut  |  AI assistance disclosed in docs/AI_ASSISTANCE.md",48,65,860,11,MUTED)
    c.save()
    extracted = "\n".join(p.extract_text() for p in PdfReader(OUTPUT).pages)
    for required in ["problem", "solution", "Users", "Market", "Technology", "dependencies", "Launch", "growth", "Round 2", "BHASHINI", "5%"]:
        assert required.lower() in extracted.lower(), required
    assert len(PdfReader(OUTPUT).pages)==7
    (ROOT/"pitch/pitch_content.md").write_text("# SolliCut pitch content\n\n"+"\n\n".join(content),encoding="utf-8")
    print(f"Generated {OUTPUT}; all 7 pages have extractable text and required sections.")


if __name__ == "__main__":
    build()


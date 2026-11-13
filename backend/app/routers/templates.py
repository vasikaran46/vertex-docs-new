import base64
import binascii
import io
from xml.sax.saxutils import escape
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle,getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as PdfImage,Paragraph,SimpleDocTemplate,Spacer,Table,TableStyle
from PIL import Image,UnidentifiedImageError
from ..schemas import TemplateRenderIn
from ..security import current_user

router=APIRouter(prefix="/api/templates",tags=["Templates"])
ACCENTS={
    "forest":"#3D855B",
    "rose":"#B65379",
    "graphite":"#737D90",
    "cocoa":"#9B6B46",
    "amber":"#9C7D27",
    "ocean":"#438794",
}

def safe_paragraph(value:str,style:ParagraphStyle):
    return Paragraph(escape(value).replace("\n","<br/>"),style)

def profile_photo(photo_data:str|None):
    if not photo_data:
        return None
    try:
        decoded=base64.b64decode(photo_data,validate=True)
        if len(decoded)>2*1024*1024:
            raise ValueError("Photo must be 2 MB or smaller")
        image=Image.open(io.BytesIO(decoded))
        if image.format not in {"PNG","JPEG","WEBP"} or image.width*image.height>20_000_000:
            raise ValueError("Use a PNG, JPEG, or WebP photo under 20 megapixels")
        image.thumbnail((1200,1600))
        if "A" in image.getbands():
            background=Image.new("RGB",image.size,"white")
            background.paste(image,mask=image.getchannel("A"))
            image=background
        else:
            image=image.convert("RGB")
        output=io.BytesIO()
        image.save(output,format="PNG")
        output.seek(0)
        return output
    except (binascii.Error,ValueError,OSError,UnidentifiedImageError,Image.DecompressionBombError) as error:
        raise HTTPException(400,"The profile photo must be a valid PNG, JPEG, or WebP image smaller than 2 MB") from error

@router.post("/render")
def render_template(x:TemplateRenderIn,u=Depends(current_user)):
    buffer=io.BytesIO()
    compact=x.layout=="compact"
    margin=14*mm if compact else 19*mm
    document=SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=margin,
        leftMargin=margin,
        topMargin=16*mm,
        bottomMargin=18*mm,
        title=x.title or x.template.replace("-"," ").title(),
        author=x.full_name or "Vertex Docs",
    )
    accent=colors.HexColor(ACCENTS[x.accent])
    samples=getSampleStyleSheet()
    title_font="Times-Bold" if x.layout=="classic" else "Helvetica-Bold"
    styles={
        "title":ParagraphStyle("VertexTitle",parent=samples["Title"],fontName=title_font,fontSize=24 if not compact else 20,leading=29,textColor=accent,alignment=TA_LEFT,spaceAfter=5),
        "subtitle":ParagraphStyle("VertexSubtitle",parent=samples["Normal"],fontSize=10,leading=14,textColor=colors.HexColor("#5E6870"),spaceAfter=9),
        "heading":ParagraphStyle("VertexHeading",parent=samples["Heading2"],fontName="Helvetica-Bold",fontSize=11,leading=14,textColor=accent,spaceBefore=10,spaceAfter=4),
        "body":ParagraphStyle("VertexBody",parent=samples["BodyText"],fontName="Helvetica",fontSize=9.5 if not compact else 9,leading=14 if not compact else 12,spaceAfter=6),
        "small":ParagraphStyle("VertexSmall",parent=samples["BodyText"],fontSize=8.5,leading=12,textColor=colors.HexColor("#59636B"),spaceAfter=3),
    }
    story=[]
    content_width=A4[0]-2*margin
    def heading(value:str):
        story.append(safe_paragraph(value,styles["heading"]))
    def body(value:str):
        if value.strip():
            story.append(safe_paragraph(value,styles["body"]))
    def section(label:str,value:str):
        if value.strip():
            heading(label)
            body(value)
    if x.template=="resume":
        profile=[safe_paragraph(x.full_name or "Your Name",styles["title"])]
        if x.title:profile.append(safe_paragraph(x.title,styles["subtitle"]))
        photo=profile_photo(x.photo_data)
        if photo:
            header=Table([[profile,PdfImage(photo,width=31*mm,height=38*mm,kind="proportional")]],colWidths=[content_width-37*mm,37*mm])
            header.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("ALIGN",(1,0),(1,0),"RIGHT"),("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
            story.append(header)
        else:
            story.extend(profile)
        contacts=[item for item in (x.email,x.phone,x.location,x.website) if item.strip()]
        if contacts:story.append(safe_paragraph("  |  ".join(contacts),styles["small"]))
        section("Professional summary",x.summary)
        section("Experience",x.experience)
        section("Education",x.education)
        section("Skills",x.skills)
    elif x.template in ("cover-letter","business-letter"):
        label="Cover Letter" if x.template=="cover-letter" else "Business Letter"
        story.append(safe_paragraph(x.title or label,styles["title"]))
        if x.date:story.append(safe_paragraph(x.date,styles["subtitle"]))
        if x.recipient:body(x.recipient)
        if x.company:body(x.company)
        if x.subject:heading(x.subject)
        body(x.body)
        if x.full_name:story.extend([Spacer(1,8),safe_paragraph(x.full_name,styles["body"])])
        if x.email:story.append(safe_paragraph(x.email,styles["small"]))
    elif x.template=="meeting-notes":
        story.append(safe_paragraph(x.title or "Meeting Notes",styles["title"]))
        if x.date:story.append(safe_paragraph(x.date,styles["subtitle"]))
        section("Meeting summary",x.summary)
        section("Agenda and notes",x.body)
        section("Attendees",x.recipient)
        section("Action items",x.experience)
    elif x.template=="project-proposal":
        story.append(safe_paragraph(x.title or "Project Proposal",styles["title"]))
        if x.company:story.append(safe_paragraph(x.company,styles["subtitle"]))
        section("Overview",x.summary)
        section("Proposal",x.body)
        section("Deliverables and timeline",x.experience)
        section("Team and skills",x.skills)
        section("Education and references",x.education)
    else:
        story.append(safe_paragraph(x.title or "Invoice",styles["title"]))
        if x.company:story.append(safe_paragraph(x.company,styles["subtitle"]))
        details=[item for item in (x.full_name,x.email,x.location,x.date) if item.strip()]
        if details:
            table=Table([[safe_paragraph(item,styles["small"]) for item in details]],colWidths=[content_width/len(details)]*len(details))
            table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#F0F3F4")),("BOX",(0,0),(-1,-1),.5,colors.HexColor("#D7DEE1")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
            story.extend([Spacer(1,8),table])
        section("Bill to",x.recipient)
        heading("Items and details")
        body(x.body)
        section("Notes",x.summary)
    if len(story)==0:
        story.append(safe_paragraph(x.title or "Document",styles["title"]))
    def footer(canvas,doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D7DEE1"))
        canvas.line(margin,12*mm,A4[0]-margin,12*mm)
        canvas.setFillColor(colors.HexColor("#737D84"))
        canvas.setFont("Helvetica",8)
        canvas.drawString(margin,8*mm,"Created with Vertex Docs")
        canvas.drawRightString(A4[0]-margin,8*mm,str(doc.page))
        canvas.restoreState()
    document.build(story,onFirstPage=footer,onLaterPages=footer)
    buffer.seek(0)
    filename=f"vertex-{x.template}.pdf"
    return StreamingResponse(buffer,media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="{filename}"'})

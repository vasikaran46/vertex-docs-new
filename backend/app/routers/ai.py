import asyncio,base64,binascii,io,os,zipfile,httpx
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,File,Form,UploadFile
from pypdf import PdfReader
from PIL import Image,UnidentifiedImageError
from sqlalchemy import desc
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AssistantConversation,AssistantMessage,Document
from ..security import current_user
from ..schemas import ChatIn,DocumentChatIn,DocumentLanguageIn,DocumentTranslationIn,TranslationIn
router=APIRouter(prefix="/api/ai",tags=["AI"])
STORE=Path(__file__).resolve().parents[2]/"storage"
LANGUAGE_NAMES={
    "en":"English","ta":"Tamil","hi":"Hindi","ml":"Malayalam","te":"Telugu","kn":"Kannada",
    "ja":"Japanese","de":"German","sa":"Sanskrit","bn":"Bengali","fr":"French","es":"Spanish",
    "tanglish":"Tanglish",
}
SOURCE_LANGUAGES={"auto",*LANGUAGE_NAMES}
MAX_TEXT_CHARS=20000
TRANSLATION_CHUNK_CHARS=4000
TRANSLATION_CONCURRENCY=4

def extract_text(filename:str,content:bytes)->str:
    extension=Path(filename).suffix.lower()
    try:
        if extension==".pdf":
            reader=PdfReader(io.BytesIO(content))
            text="\n\n".join(page.extract_text() or "" for page in reader.pages)
        elif extension==".docx":
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                root=ET.fromstring(archive.read("word/document.xml"))
            namespace={"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            paragraphs=["".join(node.itertext()) for node in root.findall(".//w:p",namespace)]
            text="\n".join(paragraphs)
        elif extension in {".txt",".md"}:
            text=content.decode("utf-8-sig")
        else:
            raise HTTPException(415,"Use a PDF, DOCX, TXT, or Markdown document")
    except HTTPException:
        raise
    except (OSError,ValueError,zipfile.BadZipFile,ET.ParseError):
        raise HTTPException(400,"The document could not be read")
    if not text.strip():
        raise HTTPException(400,"No readable text was found in the document")
    if len(text)>MAX_TEXT_CHARS:
        raise HTTPException(413,"The extracted text is over the 20,000 character AI limit")
    return text

def owned_document_text(doc_id:int,db:Session,u)->str:
    item=db.query(Document).filter_by(id=doc_id,owner_id=u.id).first()
    if not item:
        raise HTTPException(404,"Document not found")
    path=STORE/item.stored_name
    if not path.is_file():
        raise HTTPException(404,"Document file is no longer available")
    try:
        content=path.read_bytes()
    except OSError:
        raise HTTPException(500,"The document could not be opened")
    return extract_text(item.original_name,content)

async def ai_completion(messages:list[dict])->str:
    key=os.getenv("LLM_API_KEY","").strip()
    if not key:
        raise HTTPException(503,"Add LLM_API_KEY to backend/.env")
    base=os.getenv("LLM_BASE_URL","https://api.openai.com/v1").rstrip("/")
    model=os.getenv("LLM_MODEL","gpt-4o-mini")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response=await client.post(
                base+"/chat/completions",
                headers={"Authorization":"Bearer "+key},
                json={"model":model,"messages":messages},
            )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except (httpx.RequestError,httpx.HTTPStatusError,KeyError,ValueError,TypeError) as error:
        raise HTTPException(502,"AI provider request failed") from error

async def translate_text(x:TranslationIn):
    source=LANGUAGE_NAMES.get(x.source_language,"any language")
    target=LANGUAGE_NAMES[x.target_language]
    tanglish_rule=" Use natural spoken Tamil expressed in Latin letters, mixed with common English words; do not use Tamil script." if x.target_language=="tanglish" else ""
    system_message=f"Translate the user's text into {target}. The source is {source}; if it is auto, identify it. Preserve meaning, names, formatting, and tone. Return only the translation.{tanglish_rule}"
    chunks=[]
    start=0
    while start<len(x.text):
        end=min(start+TRANSLATION_CHUNK_CHARS,len(x.text))
        if end<len(x.text):
            boundary=x.text.rfind("\n\n",start,end)
            if boundary<=start+TRANSLATION_CHUNK_CHARS//2:
                boundary=x.text.rfind("\n",start,end)
            if boundary<=start+TRANSLATION_CHUNK_CHARS//2:
                boundary=x.text.rfind(" ",start,end)
            if boundary>start+TRANSLATION_CHUNK_CHARS//2:
                end=boundary
        chunks.append(x.text[start:end].strip())
        start=end
        while start<len(x.text) and x.text[start].isspace():
            start+=1

    semaphore=asyncio.Semaphore(TRANSLATION_CONCURRENCY)
    async def translate_chunk(chunk:str)->str:
        async with semaphore:
            return await ai_completion([
                {"role":"system","content":system_message},
                {"role":"user","content":chunk},
            ])

    translated=await asyncio.gather(*(translate_chunk(chunk) for chunk in chunks))
    translation="\n\n".join(part.strip() for part in translated)
    return {"translation":translation,"source_language":x.source_language,"target_language":x.target_language}

def owned_conversation(conversation_id:int,db:Session,u)->AssistantConversation:
    conversation=db.query(AssistantConversation).filter_by(id=conversation_id,owner_id=u.id).first()
    if not conversation:
        raise HTTPException(404,"Chat not found")
    return conversation

@router.get("/conversations")
def list_conversations(db:Session=Depends(get_db),u=Depends(current_user)):
    items=db.query(AssistantConversation).filter_by(owner_id=u.id).order_by(desc(AssistantConversation.updated_at)).limit(50).all()
    return [{"id":item.id,"title":item.title,"updated_at":item.updated_at} for item in items]

@router.post("/conversations")
def create_conversation(db:Session=Depends(get_db),u=Depends(current_user)):
    conversation=AssistantConversation(owner_id=u.id,title="New chat")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return {"id":conversation.id,"title":conversation.title,"updated_at":conversation.updated_at}

@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id:int,db:Session=Depends(get_db),u=Depends(current_user)):
    conversation=owned_conversation(conversation_id,db,u)
    messages=db.query(AssistantMessage).filter_by(conversation_id=conversation.id).order_by(AssistantMessage.id).all()
    return {
        "id":conversation.id,
        "title":conversation.title,
        "messages":[{"id":item.id,"role":item.role,"text":item.content,"created_at":item.created_at} for item in messages],
    }

@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id:int,db:Session=Depends(get_db),u=Depends(current_user)):
    conversation=owned_conversation(conversation_id,db,u)
    db.query(AssistantMessage).filter_by(conversation_id=conversation.id).delete()
    db.delete(conversation)
    db.commit()
    return {"success":True}

@router.post("/chat/attachment-text")
async def chat_attachment_text(file:UploadFile=File(...),u=Depends(current_user)):
    limit=int(os.getenv("MAX_UPLOAD_MB","50"))*1024*1024
    content=await file.read(limit+1)
    if len(content)>limit:
        raise HTTPException(413,"File too large")
    text=await asyncio.to_thread(extract_text,file.filename or "",content)
    return {"name":Path(file.filename or "document").name,"text":text[:12000]}

def validated_chat_image(image_data:str,media_type:str)->str:
    try:
        decoded=base64.b64decode(image_data,validate=True)
        if len(decoded)>4*1024*1024:
            raise ValueError()
        image=Image.open(io.BytesIO(decoded))
        expected={"image/png":"PNG","image/jpeg":"JPEG","image/webp":"WEBP"}
        if image.format!=expected[media_type] or image.width*image.height>20_000_000:
            raise ValueError()
        image.verify()
        return base64.b64encode(decoded).decode("ascii")
    except (binascii.Error,ValueError,OSError,UnidentifiedImageError,Image.DecompressionBombError) as error:
        raise HTTPException(400,"Attach a valid PNG, JPEG, or WebP image smaller than 4 MB") from error

@router.post("/chat")
async def chat(x:ChatIn,db:Session=Depends(get_db),u=Depends(current_user)):
    reply_language="Tanglish (spoken Tamil in Latin letters mixed with common English words)" if x.language=="tanglish" else x.language
    msgs=[{"role":"system","content":f"You are Vertex Docs Assistant. Help with document workflows. Reply in {reply_language} where possible. Never claim an operation succeeded unless confirmed."}]
    if x.context:msgs.append({"role":"system","content":"Document context:\n"+x.context})
    conversation=owned_conversation(x.conversation_id,db,u) if x.conversation_id else AssistantConversation(owner_id=u.id,title="New chat")
    if not x.conversation_id:
        db.add(conversation)
        db.flush()
    previous=db.query(AssistantMessage).filter_by(conversation_id=conversation.id).order_by(desc(AssistantMessage.id)).limit(12).all()
    if previous:
        msgs.extend({"role":item.role,"content":item.content} for item in reversed(previous))
    else:
        msgs.extend({"role":turn.role,"content":turn.content} for turn in x.history)
    user_content: str|list[dict]=x.message
    if x.image_data:
        encoded=validated_chat_image(x.image_data,x.image_media_type)
        user_content=[
            {"type":"text","text":x.message},
            {"type":"image_url","image_url":{"url":f"data:{x.image_media_type};base64,{encoded}"}},
        ]
    msgs.append({"role":"user","content":user_content})
    reply=await ai_completion(msgs)
    if conversation.title=="New chat":
        conversation.title=x.message.strip()[:117] + ("…" if len(x.message.strip())>117 else "")
    conversation.updated_at=datetime.utcnow()
    db.add(AssistantMessage(conversation_id=conversation.id,role="user",content=x.message))
    db.add(AssistantMessage(conversation_id=conversation.id,role="assistant",content=reply))
    db.commit()
    return {"reply":reply,"conversation_id":conversation.id,"title":conversation.title}

@router.post("/documents/{doc_id}/summarize")
async def summarize_document(
    doc_id:int,
    x:DocumentLanguageIn,
    db:Session=Depends(get_db),
    u=Depends(current_user),
):
    text=owned_document_text(doc_id,db,u)
    language="Tanglish (spoken Tamil written in Latin letters mixed with English)" if x.language=="tanglish" else LANGUAGE_NAMES[x.language]
    reply=await ai_completion([
        {"role":"system","content":f"Summarize the document accurately in {language}. Use a brief overview, key points, and any actions or dates. Do not invent details."},
        {"role":"user","content":text},
    ])
    return {"summary":reply,"language":x.language}

@router.post("/documents/{doc_id}/chat")
async def chat_with_document(
    doc_id:int,
    x:DocumentChatIn,
    db:Session=Depends(get_db),
    u=Depends(current_user),
):
    text=owned_document_text(doc_id,db,u)
    language="Tanglish (spoken Tamil in Latin letters mixed with common English words)" if x.language=="tanglish" else LANGUAGE_NAMES[x.language]
    msgs=[
        {"role":"system","content":f"You are Vertex Docs Assistant. Answer the user's questions using the selected document context. Reply in {language}. If the answer is not in the document, say so instead of guessing."},
        {"role":"system","content":"Selected document context:\n"+text},
    ]
    msgs.extend({"role":turn.role,"content":turn.content} for turn in x.history)
    msgs.append({"role":"user","content":x.message})
    return {"reply":await ai_completion(msgs)}

@router.post("/question-generator")
async def generate_document_questions(
    file:UploadFile=File(...),
    count:int=Form(5),
    language:str=Form("en"),
    u=Depends(current_user),
):
    if not 1<=count<=20:
        raise HTTPException(400,"Choose between 1 and 20 questions.")
    if language not in LANGUAGE_NAMES:
        raise HTTPException(400,"Choose a supported question language.")
    content=await file.read(50*1024*1024+1)
    if len(content)>50*1024*1024:
        raise HTTPException(413,"Files must be 50 MB or smaller")
    text=extract_text(file.filename or "document.pdf",content)
    language_name="Tanglish (spoken Tamil in Latin letters mixed with English)" if language=="tanglish" else LANGUAGE_NAMES[language]
    reply=await ai_completion([
        {"role":"system","content":f"Create exactly {count} clear study questions from the provided document, in {language_name}. Use only facts in the document. Number each question. Add a concise answer key after the questions, clearly separated."},
        {"role":"user","content":text},
    ])
    return {"questions":reply,"count":count,"language":language}

@router.post("/documents/{doc_id}/translate")
async def translate_document(
    doc_id:int,
    x:DocumentTranslationIn,
    db:Session=Depends(get_db),
    u=Depends(current_user),
):
    text=owned_document_text(doc_id,db,u)
    request=TranslationIn(text=text,source_language=x.source_language,target_language=x.target_language)
    return await translate_text(request)

@router.post("/translate")
async def translate(x:TranslationIn,u=Depends(current_user)):
    return await translate_text(x)

@router.post("/translate-file")
async def translate_file(
    file:UploadFile=File(...),
    source_language:str=Form("auto"),
    target_language:str=Form(...),
    u=Depends(current_user),
):
    if source_language not in SOURCE_LANGUAGES or target_language not in LANGUAGE_NAMES:
        raise HTTPException(400,"Choose one of the supported source and target languages")
    content=await file.read(int(os.getenv("MAX_UPLOAD_MB","50"))*1024*1024+1)
    if len(content)>int(os.getenv("MAX_UPLOAD_MB","50"))*1024*1024:
        raise HTTPException(413,"File too large")
    text=extract_text(file.filename or "",content)
    request=TranslationIn(text=text,source_language=source_language,target_language=target_language)
    return await translate_text(request)

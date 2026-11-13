import base64
import io
from docx import Document as WordDocument
from PIL import Image
import pymupdf
from pypdf import PdfReader,PdfWriter
from reportlab.pdfgen import canvas as pdf_canvas
from tests.support import ApiTestCase


class EditorExportTests(ApiTestCase):
    def blank_pdf(self):
        writer=PdfWriter()
        writer.add_blank_page(width=200,height=300)
        output=io.BytesIO()
        writer.write(output)
        return output.getvalue()

    def uncompressed_pdf(self):
        output=io.BytesIO()
        document=pdf_canvas.Canvas(output,pagesize=(200,300),pageCompression=0)
        for _ in range(500):
            document.drawString(10,290,"Repeated content stream text " * 5)
        document.showPage()
        document.save()
        return output.getvalue()

    def png_data(self):
        image=Image.new("RGB",(24,32),"#34734b")
        output=io.BytesIO()
        image.save(output,format="PNG")
        return base64.b64encode(output.getvalue()).decode("ascii")

    def test_preview_renders_an_authenticated_pdf_page(self):
        _,token=self.create_account()
        response=self.client.post(
            "/api/pdf/preview",
            headers={"Authorization":f"Bearer {token}"},
            data={"page":"1"},
            files={"file":("page.pdf",self.blank_pdf(),"application/pdf")},
        )
        self.assertEqual(response.status_code,200,response.text)
        result=response.json()
        self.assertEqual((result["page_number"],result["page_count"]),(1,1))
        image=Image.open(io.BytesIO(base64.b64decode(result["image_data"])))
        self.assertEqual(image.format,"PNG")
        self.assertGreater(image.width,0)
        self.assertGreater(image.height,0)

    def test_annotation_is_embedded_in_the_requested_pdf_page(self):
        _,token=self.create_account()
        writer=PdfWriter()
        writer.add_blank_page(width=200,height=300)
        writer.add_blank_page(width=200,height=300)
        source=io.BytesIO()
        writer.write(source)
        response=self.client.post(
            "/api/pdf/annotate",
            headers={"Authorization":f"Bearer {token}"},
            data={"page":"2","overlay_data":self.png_data()},
            files={"file":("pages.pdf",source.getvalue(),"application/pdf")},
        )
        self.assertEqual(response.status_code,200,response.text)
        edited=pymupdf.open(stream=response.content,filetype="pdf")
        self.assertEqual(edited.page_count,2)
        self.assertEqual(len(edited[0].get_images()),0)
        self.assertGreater(len(edited[1].get_images()),0)
        edited.close()

    def test_compress_returns_a_readable_pdf(self):
        _,token=self.create_account()
        source=self.uncompressed_pdf()
        response=self.client.post(
            "/api/pdf/compress",
            headers={"Authorization":f"Bearer {token}"},
            files={"file":("page.pdf",source,"application/pdf")},
        )
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.headers["content-type"],"application/pdf")
        self.assertEqual(len(PdfReader(io.BytesIO(response.content)).pages),1)
        self.assertLess(len(response.content),len(source))

    def test_compress_reduces_image_heavy_pdf_size(self):
        _,token=self.create_account()
        image=Image.effect_noise((1200,1600),100).convert("RGB")
        image_data=io.BytesIO()
        image.save(image_data,format="JPEG",quality=94)
        document=pymupdf.open()
        page=document.new_page(width=400,height=550)
        page.insert_image(page.rect,stream=image_data.getvalue())
        source=document.tobytes()
        document.close()
        response=self.client.post(
            "/api/pdf/compress",
            headers={"Authorization":f"Bearer {token}"},
            files={"file":("photo.pdf",source,"application/pdf")},
        )
        self.assertEqual(response.status_code,200,response.text)
        self.assertLess(len(response.content),len(source))
        compressed=pymupdf.open(stream=response.content,filetype="pdf")
        self.assertEqual(compressed.page_count,1)
        self.assertTrue(compressed[0].get_images())
        compressed.close()

    def test_compress_meets_requested_maximum_and_reports_actual_size(self):
        _,token=self.create_account()
        source=self.uncompressed_pdf()
        target=len(source)
        response=self.client.post(
            "/api/pdf/compress",
            headers={"Authorization":f"Bearer {token}"},
            data={"target_size_bytes":str(target)},
            files={"file":("page.pdf",source,"application/pdf")},
        )
        self.assertEqual(response.status_code,200,response.text)
        self.assertLessEqual(len(response.content),target)
        self.assertLessEqual(len(response.content),len(source))
        self.assertEqual(response.headers["X-Compression-Actual-Bytes"],str(len(response.content)))
        self.assertEqual(response.headers["X-Compression-Target-Bytes"],str(target))
        self.assertEqual(len(PdfReader(io.BytesIO(response.content)).pages),1)

    def test_compress_reports_when_target_cannot_be_met_without_rasterization(self):
        _,token=self.create_account()
        response=self.client.post(
            "/api/pdf/compress",
            headers={"Authorization":f"Bearer {token}"},
            data={"target_size_bytes":"1"},
            files={"file":("page.pdf",self.uncompressed_pdf(),"application/pdf")},
        )
        self.assertEqual(response.status_code,422)
        self.assertIn("smallest result",response.json()["detail"])
        self.assertIn("rasterization",response.json()["detail"])

    def test_compress_can_rasterize_pages_to_meet_a_tight_target(self):
        _,token=self.create_account()
        image=Image.effect_noise((1200,1600),100).convert("RGB")
        image_data=io.BytesIO()
        image.save(image_data,format="JPEG",quality=94)
        document=pymupdf.open()
        page=document.new_page(width=400,height=550)
        page.insert_text((40,60),"Flattening is optional")
        page.insert_image(page.rect,stream=image_data.getvalue())
        source=document.tobytes()
        document.close()
        target=10*1024
        response=self.client.post(
            "/api/pdf/compress",
            headers={"Authorization":f"Bearer {token}"},
            data={"target_size_bytes":str(target),"rasterize_if_needed":"true"},
            files={"file":("photo.pdf",source,"application/pdf")},
        )
        self.assertEqual(response.status_code,200,response.text)
        self.assertLessEqual(len(response.content),target)
        self.assertEqual(response.headers["X-Compression-Mode"],"rasterized")
        flattened=pymupdf.open(stream=response.content,filetype="pdf")
        self.assertEqual(flattened[0].get_text().strip(),"")
        flattened.close()

    def test_exports_pdf_docx_and_text_with_authenticated_backend(self):
        _,token=self.create_account()
        auth={"Authorization":f"Bearer {token}"}
        image_data=self.png_data()

        pdf=self.client.post(
            "/api/pdf/editor-export",
            headers=auth,
            json={"content":"Page content","output_format":"pdf","page_preview_data":image_data},
        )
        self.assertEqual(pdf.status_code,200,pdf.text)
        self.assertEqual(pdf.headers["content-type"],"application/pdf")
        self.assertEqual(len(PdfReader(io.BytesIO(pdf.content)).pages),1)

        docx=self.client.post(
            "/api/pdf/editor-export",
            headers=auth,
            json={"content":"Editable document text","output_format":"docx","image_data":image_data},
        )
        self.assertEqual(docx.status_code,200,docx.text)
        word_document=WordDocument(io.BytesIO(docx.content))
        self.assertEqual(word_document.paragraphs[0].text,"Editable document text")
        self.assertEqual(len(word_document.inline_shapes),1)

        text=self.client.post(
            "/api/pdf/editor-export",
            headers=auth,
            json={"content":"Plain text output","output_format":"txt"},
        )
        self.assertEqual(text.status_code,200,text.text)
        self.assertEqual(text.content.decode("utf-8"),"Plain text output")

    def test_text_export_rejects_images_instead_of_silently_dropping_them(self):
        _,token=self.create_account()
        response=self.client.post(
            "/api/pdf/editor-export",
            headers={"Authorization":f"Bearer {token}"},
            json={"content":"Text","output_format":"txt","image_data":self.png_data()},
        )
        self.assertEqual(response.status_code,400)
        self.assertIn("cannot include images",response.json()["detail"])

    def test_convert_endpoint_converts_an_image_to_pdf(self):
        _,token=self.create_account()
        image=Image.new("RGB",(24,32),"#527fac")
        data=io.BytesIO()
        image.save(data,format="PNG")
        response=self.client.post(
            "/api/pdf/convert",
            headers={"Authorization":f"Bearer {token}"},
            data={"output_format":"pdf"},
            files={"file":("page.png",data.getvalue(),"image/png")},
        )
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.headers["content-type"],"application/pdf")
        self.assertEqual(len(PdfReader(io.BytesIO(response.content)).pages),1)

import { PDFDocument, rgb, StandardFonts } from 'pdf-lib';
import { PDFElement } from '../store/useStore';

export async function processPDF(originalBase64: string, elements: PDFElement[], pageDimensions: { width: number; height: number }[]) {
  const pdfDoc = await PDFDocument.load(originalBase64);
  const form = pdfDoc.getForm();
  const pages = pdfDoc.getPages();
  const font = await pdfDoc.embedFont(StandardFonts.Helvetica);

  for (const el of elements) {
    const page = pages[el.page];
    const { width: pdfWidth, height: pdfHeight } = page.getSize();
    const { width: canvasWidth, height: canvasHeight } = pageDimensions[el.page];

    // Scale coordinates
    const scaleX = pdfWidth / canvasWidth;
    const scaleY = pdfHeight / canvasHeight;

    const x = el.x * scaleX;
    const y = pdfHeight - (el.y * scaleY) - (el.height * scaleY); // PDF origin is bottom-left
    const width = el.width * scaleX;
    const height = el.height * scaleY;

    switch (el.type) {
      case 'whiteout':
        page.drawRectangle({
          x,
          y,
          width,
          height,
          color: rgb(1, 1, 1),
          borderColor: el.hasBorder ? rgb(0, 0, 0) : undefined,
          borderWidth: el.hasBorder ? 1 : 0,
        });
        break;

      case 'static_text':
        page.drawText(el.text || '', {
          x: x + 2,
          y: y + height - 12,
          size: 10,
          font,
          color: rgb(0, 0, 0),
          maxWidth: width,
        });
        break;

      case 'text':
      case 'textarea': {
        const textField = form.createTextField(`${el.type}_${el.id}`);
        textField.setText('');
        textField.addToPage(page, { 
          x, y, width, height, 
          backgroundColor: rgb(0.86, 0.92, 0.99), // Light blue #dbeafe
          borderColor: el.hasBorder ? rgb(0, 0, 0) : undefined,
        });
        if (el.type === 'textarea') {
          textField.enableMultiline();
        }
        break;
      }

      case 'checkbox': {
        const checkBox = form.createCheckBox(`checkbox_${el.id}`);
        checkBox.addToPage(page, { x, y, width, height });
        break;
      }

      case 'dropdown': {
        const dropdown = form.createDropdown(`dropdown_${el.id}`);
        dropdown.setOptions(el.options || []);
        dropdown.addToPage(page, { x, y, width, height });
        break;
      }

      case 'signature': {
        // pdf-lib does not support creating NEW signature fields directly via form.createSignature
        // We use a readonly text field as a placeholder or a generic field.
        const signatureField = form.createTextField(`signature_${el.id}`);
        signatureField.addToPage(page, { 
          x, y, width, height,
          backgroundColor: rgb(1, 0.92, 0.61), // Opaque yellow
        });
        break;
      }
    }
  }

  const pdfBytes = await pdfDoc.save();
  return btoa(String.fromCharCode(...new Uint8Array(pdfBytes)));
}

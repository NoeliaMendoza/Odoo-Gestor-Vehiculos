import io
import html
import base64
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def escape(text):
    return html.escape(str(text)) if text else ''

def build_pdf(data):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=36)
    styles = getSampleStyleSheet()

    sheyla_blue = "#00AEEF" # Cyan blue from logo
    sheyla_dark = "#007BA7" # Darker cyan

    # Common styles
    normal_style = ParagraphStyle('TimesNormal', parent=styles['Normal'], fontName='Times-Roman', fontSize=11, leading=14)
    normal_bold_style = ParagraphStyle('TimesNormalBold', parent=normal_style, fontName='Times-Bold')
    center_style = ParagraphStyle('Center', parent=normal_style, alignment=1)

    title_blue_style = ParagraphStyle(
        'TitleBlue', parent=styles['Heading1'], fontName='Times-Bold', fontSize=16,
        textColor=colors.HexColor(sheyla_blue), alignment=1, spaceAfter=15
    )

    report_title_style = ParagraphStyle(
        'ReportTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=14,
        textColor=colors.HexColor(sheyla_dark), alignment=1, spaceAfter=2
    )
    report_subtitle_style = ParagraphStyle(
        'ReportSubtitle', parent=normal_style, fontName='Helvetica', fontSize=10,
        textColor=colors.HexColor(sheyla_dark), alignment=1, spaceAfter=10
    )

    section_title_style = ParagraphStyle(
        'SectionTitle', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12,
        textColor=colors.white, alignment=0, spaceAfter=6, leftIndent=5
    )

    date_style = ParagraphStyle('DateStyle', parent=normal_style, alignment=2, spaceAfter=25)

    elements = []

    def get_logo():
        if data.get('logo'):
            try:
                return Image(io.BytesIO(base64.b64decode(data['logo'])), width=130, height=40)
            except Exception:
                pass
        return Paragraph("LOGO", normal_style)

    # 1. COMPROMISO
    if data.get('kind') == 'compromiso':
        logo_img = get_logo()
        title_text = Paragraph("<b>SHEYLA SOFTWARE</b>", title_blue_style)

        if logo_img:
            header_table = Table([[logo_img, title_text]], colWidths=[150, 318])
            header_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (0,0), 'LEFT'), ('VALIGN', (0,0), (0,0), 'TOP'),
                ('ALIGN', (1,0), (1,0), 'CENTER'), ('VALIGN', (1,0), (1,0), 'TOP'),
            ]))
            elements.append(header_table)
            elements.append(Spacer(1, 15))
        else:
            elements.append(title_text)

        if data.get('date_label'):
            elements.append(Paragraph(escape(data['date_label']), date_style))

        list_counter = 1
        for p_dict in data.get('paragraphs', []):
            text_html = ""
            if isinstance(p_dict, dict):
                for run in p_dict.get('runs', []):
                    t = escape(run.get('text', '')).replace('\n', '<br/>')
                    if run.get('bold'):
                        if 'Nota:' in t: t = t.replace('Nota:', f'<font color="{sheyla_blue}">Nota:</font>')
                        if 'Recordatorio:' in t: t = t.replace('Recordatorio:', f'<font color="{sheyla_blue}">Recordatorio:</font>')
                        t = f"<b>{t}</b>"
                    else:
                        if t.startswith('Nota:'): t = t.replace('Nota:', f'<font color="{sheyla_blue}"><b>Nota:</b></font>')
                        if t.startswith('Recordatorio:'): t = t.replace('Recordatorio:', f'<font color="{sheyla_blue}"><b>Recordatorio:</b></font>')
                    text_html += t

                p_style = center_style if p_dict.get('center') else normal_style
                if p_dict.get('listed'):
                    text_html = f"&nbsp;&nbsp;&nbsp;&nbsp;{list_counter}. &nbsp;&nbsp;" + text_html
                    list_counter += 1
                elements.append(Paragraph(text_html, p_style))
                elements.append(Spacer(1, 10))
            else:
                elements.append(Paragraph(escape(p_dict), normal_style))
                elements.append(Spacer(1, 10))

        if data.get('signatures'):
            elements.append(Spacer(1, 60))
            sig_data = [["_________________________________", "_________________________________"]]
            labels = [f"<b>{escape(sig[0])}</b>" for sig in data['signatures']]
            names = [escape(sig[1]) for sig in data['signatures']]
            sig_data.append([Paragraph(n, center_style) for n in names])
            sig_data.append([Paragraph(l, center_style) for l in labels])
            t = Table(sig_data, colWidths=[234, 234])
            t.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
            elements.append(t)

    # 2. REPORTE
    else:
        # Professional Header for Reporte using Sheyla colors
        logo_img = get_logo()

        info_html = f'''
        <b>Folio:</b> {escape(data.get('folio', ''))}<br/>
        <b>Fecha:</b> {escape(data.get('generated', ''))}
        '''
        info_p = Paragraph(info_html, normal_style)

        # We removed the huge "REPORTE DE USO VEHICULAR" subtitle / title string to keep it clean like the other doc
        # Actually the user said: "quita este titulo: Asignación, recorrido y devolución y Estado: Devuelto."
        # So we will just use SHEYLA SOFTWARE as title.
        title_text = Paragraph("<b>SHEYLA SOFTWARE</b>", title_blue_style)

        header_table = Table([[logo_img, title_text, info_p]], colWidths=[130, 260, 130])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (0,0), 'LEFT'), ('VALIGN', (0,0), (0,0), 'MIDDLE'),
            ('ALIGN', (1,0), (1,0), 'CENTER'), ('VALIGN', (1,0), (1,0), 'MIDDLE'),
            ('ALIGN', (2,0), (2,0), 'RIGHT'), ('VALIGN', (2,0), (2,0), 'MIDDLE'),
            ('LINEBELOW', (0,0), (-1,-1), 1, colors.HexColor(sheyla_blue)),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10)
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 15))

        for sec in data.get('sections', []):
            # Section Header (Sheyla Blue background)
            sec_title = Table([[Paragraph(escape(sec.get('title', '')), section_title_style)]], colWidths=[520])
            sec_title.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor(sheyla_blue)), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
            elements.append(sec_title)
            elements.append(Spacer(1, 8))

            for p in sec.get('paragraphs', []):
                elements.append(Paragraph(escape(p), normal_style))
                elements.append(Spacer(1, 4))

            if sec.get('rows'):
                t_data = []
                if sec.get('headers'):
                    t_data.append([Paragraph(f"<b>{escape(h)}</b>", normal_style) for h in sec.get('headers')])
                for r in sec.get('rows'):
                    t_data.append([Paragraph(escape(str(c)), normal_style) for c in r])

                col_w = [520 / len(t_data[0])] * len(t_data[0]) if t_data else None
                t = Table(t_data, colWidths=col_w)
                # Removed grid/boxes to keep it clean as requested: "Trata de no usar muchas tablas o lineas"
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#ECF0F1")) if sec.get('headers') else ('', (0,0), (0,0), ''),
                    ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.lightgrey), # Just a subtle line below rows
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('TOPPADDING', (0,0), (-1,-1), 4),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ]))
                elements.append(t)
                elements.append(Spacer(1, 10))

            # Gauges Images
            if sec.get('gauges'):
                gauge_cells = []
                for g in sec.get('gauges'):
                    img_flowable = None
                    if g.get('image'):
                        try:
                            img_data = base64.b64decode(g['image'])
                            img_io = io.BytesIO(img_data)
                            # Render image at 160x80
                            img_flowable = Image(img_io, width=160, height=80)
                        except Exception:
                            img_flowable = Paragraph("Error de imagen", normal_style)

                    label_p = Paragraph(f"<b>{escape(g['label'])}</b>", center_style)

                    # REMOVED redundant description % as it's baked into the image
                    # desc_p = Paragraph(f"{escape(g['description'])}", center_style)

                    cell_table = Table([[label_p], [img_flowable]], colWidths=[180])
                    cell_table.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
                    gauge_cells.append(cell_table)

                if gauge_cells:
                    # Put them side by side
                    g_table = Table([gauge_cells])
                    g_table.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
                    elements.append(g_table)
                    elements.append(Spacer(1, 15))


            # Evidencia Fotográfica
            if sec.get('photos'):
                photo_cells = []
                row = []
                for p in sec.get('photos'):
                    try:
                        img_data = base64.b64decode(p['image'])
                        img_io = io.BytesIO(img_data)

                        from PIL import Image as PILImage
                        pil_img = PILImage.open(img_io)
                        w, h = pil_img.size
                        img_io.seek(0)
                        ratio = min(220/w, 160/h)
                        img_flowable = Image(img_io, width=w*ratio, height=h*ratio)
                    except Exception:
                        img_flowable = Paragraph("Error de imagen", normal_style)

                    label_p = Paragraph(f"<b>{escape(p['label'])}</b>", center_style)
                    cell = Table([[img_flowable], [label_p]])
                    cell.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('TOPPADDING', (0,0), (-1,-1), 8), ('BOTTOMPADDING', (0,0), (-1,-1), 15)]))
                    row.append(cell)

                    if len(row) == 2:
                        photo_cells.append(row)
                        row = []

                if row:
                    row.append('')
                    photo_cells.append(row)

                p_table = Table(photo_cells, colWidths=[260, 260])
                p_table.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
                elements.append(p_table)
                elements.append(Spacer(1, 15))

        # Signatures
        if data.get('signatures'):
            elements.append(Spacer(1, 60))
            sig_data = [["_________________________________", "_________________________________"]]
            labels = [f"<b>{escape(sig[0])}</b>" for sig in data['signatures']]
            names = [escape(sig[1]) for sig in data['signatures']]
            sig_data.append([Paragraph(n, center_style) for n in names])
            sig_data.append([Paragraph(l, center_style) for l in labels])
            t = Table(sig_data, colWidths=[234, 234])
            t.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
            elements.append(t)

    doc.build(elements)
    pdf_value = buffer.getvalue()
    buffer.close()
    return pdf_value

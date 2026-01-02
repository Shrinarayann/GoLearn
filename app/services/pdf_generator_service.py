"""
PDF Generator Service.
Generates professional exam papers using FPDF2.
"""

from fpdf import FPDF
from datetime import datetime
from typing import List, Dict, Optional
import base64
import io
import logging

logger = logging.getLogger(__name__)


class ExamPDF(FPDF):
    """Custom PDF class for exam papers with header/footer."""
    
    def __init__(self, session_title: str):
        super().__init__()
        self.session_title = session_title
        self.set_auto_page_break(auto=True, margin=25)
    
    def header(self):
        """Add header to each page."""
        # GoLearn branding
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(0, 82, 204)  # #0052CC
        self.cell(0, 10, 'GoLearn Examination', align='C', new_x='LMARGIN', new_y='NEXT')
        
        # Session title
        self.set_font('Helvetica', '', 12)
        self.set_text_color(23, 43, 77)  # #172B4D
        self.cell(0, 8, self.session_title, align='C', new_x='LMARGIN', new_y='NEXT')
        
        # Date
        self.set_font('Helvetica', 'I', 10)
        self.set_text_color(107, 119, 140)  # #6B778C
        self.cell(0, 6, f"Generated: {datetime.now().strftime('%B %d, %Y')}", align='C', new_x='LMARGIN', new_y='NEXT')
        
        # Divider line
        self.set_draw_color(223, 225, 230)  # #DFE1E6
        self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
        self.ln(8)
    
    def footer(self):
        """Add footer to each page."""
        self.set_y(-20)
        self.set_font('Helvetica', 'I', 9)
        self.set_text_color(107, 119, 140)
        
        # Page number
        self.cell(0, 10, f'Page {self.page_no()}', align='C', new_x='LMARGIN', new_y='NEXT')
        
        # Branding
        self.set_font('Helvetica', '', 8)
        self.cell(0, 5, 'Powered by GoLearn - AI Study Companion', align='C')


def generate_exam_pdf(
    questions: List[Dict],
    diagram_images: Optional[Dict[str, bytes]] = None,
    session_title: str = "Examination Paper"
) -> bytes:
    """
    Generate a professional exam PDF from structured questions.
    
    Args:
        questions: List of question dicts with keys:
            - question: str
            - marks: int
            - section: str ('A', 'B', or 'C')
            - needs_diagram: bool
            - diagram_description: str (optional)
            - question_number: int
        diagram_images: Dict mapping question_number to image bytes
        session_title: Title for the exam paper
    
    Returns:
        PDF file as bytes
    """
    if diagram_images is None:
        diagram_images = {}
    
    pdf = ExamPDF(session_title)
    pdf.add_page()
    
    # Group questions by section
    sections = {
        'A': [q for q in questions if q.get('section') == 'A'],
        'B': [q for q in questions if q.get('section') == 'B'],
        'C': [q for q in questions if q.get('section') == 'C'],
    }
    
    # Instructions
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(23, 43, 77)
    pdf.cell(0, 8, 'Instructions:', new_x='LMARGIN', new_y='NEXT')
    
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(66, 82, 110)  # #42526E
    instructions = [
        "• Answer ALL questions from each section.",
        "• Section A contains 2-mark questions (short answers).",
        "• Section B contains 6-mark questions (conceptual, may include diagrams).",
        "• Section C contains 12-mark questions (analytical, may include diagrams).",
        f"• Total marks: {sum(q.get('marks', 0) for q in questions)}",
    ]
    for instruction in instructions:
        pdf.cell(0, 6, instruction, new_x='LMARGIN', new_y='NEXT')
    
    pdf.ln(8)
    
    # Section A
    if sections['A']:
        _render_section(pdf, 'A', '2-Mark Questions (Short Answers)', sections['A'], diagram_images)
    
    # Section B
    if sections['B']:
        _render_section(pdf, 'B', '6-Mark Questions (Conceptual)', sections['B'], diagram_images)
    
    # Section C
    if sections['C']:
        _render_section(pdf, 'C', '12-Mark Questions (Analytical)', sections['C'], diagram_images)
    
    # Return PDF as bytes
    return pdf.output()


def _render_section(
    pdf: ExamPDF, 
    section_letter: str, 
    section_title: str, 
    questions: List[Dict],
    diagram_images: Dict[str, bytes]
):
    """Render a section of questions."""
    # Section header
    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_text_color(0, 82, 204)  # #0052CC
    pdf.cell(0, 10, f"Section {section_letter}: {section_title}", new_x='LMARGIN', new_y='NEXT')
    
    # Divider
    pdf.set_draw_color(0, 82, 204)
    pdf.line(10, pdf.get_y(), 100, pdf.get_y())
    pdf.ln(5)
    
    for q in questions:
        question_num = q.get('question_number', 0)
        question_text = q.get('question', '')
        marks = q.get('marks', 0)
        needs_diagram = q.get('needs_diagram', False)
        
        # Question number and marks
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(23, 43, 77)
        pdf.cell(0, 8, f"Q{question_num}. [{marks} marks]", new_x='LMARGIN', new_y='NEXT')
        
        # Question text
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(66, 82, 110)
        
        # Handle multi-line questions
        pdf.multi_cell(0, 6, question_text, new_x='LMARGIN', new_y='NEXT')
        
        # Add diagram if available
        if needs_diagram and str(question_num) in diagram_images:
            try:
                image_bytes = diagram_images[str(question_num)]
                # Save to temporary file-like object
                img_stream = io.BytesIO(image_bytes)
                
                # Add image (centered, max width 120mm)
                pdf.ln(3)
                x_pos = (210 - 120) / 2  # Center on A4 page
                pdf.image(img_stream, x=x_pos, w=120)
                pdf.ln(3)
            except Exception as e:
                logger.error(f"Failed to add diagram for Q{question_num}: {e}")
                # Add placeholder text
                pdf.set_font('Helvetica', 'I', 9)
                pdf.set_text_color(107, 119, 140)
                pdf.cell(0, 6, "[Diagram placeholder - refer to study materials]", new_x='LMARGIN', new_y='NEXT')
        elif needs_diagram:
            # Diagram was expected but not generated
            pdf.set_font('Helvetica', 'I', 9)
            pdf.set_text_color(107, 119, 140)
            diagram_desc = q.get('diagram_description', 'relevant diagram')
            pdf.cell(0, 6, f"[Refer to: {diagram_desc}]", new_x='LMARGIN', new_y='NEXT')
        
        # Answer space indicator
        pdf.ln(3)
        pdf.set_font('Helvetica', 'I', 9)
        pdf.set_text_color(180, 180, 180)
        answer_lines = max(2, marks // 2)  # More space for higher mark questions
        pdf.cell(0, 5, f"(Answer space: approximately {answer_lines * 3} lines)", new_x='LMARGIN', new_y='NEXT')
        
        pdf.ln(6)
    
    pdf.ln(5)

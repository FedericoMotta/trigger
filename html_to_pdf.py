import os
from pyhtml2pdf import converter


import subprocess
import os

def html_to_pdf(html_path, pdf_path):
    # Convert to absolute paths
    html_abs = os.path.abspath(html_path)
    pdf_abs = os.path.abspath(pdf_path)
    
    # Read the HTML content
    with open(html_abs, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Remove markdown code block wrappers like ```html and ```
    html_content = html_content.replace('```html', '').replace('```', '')
    
    # Add CSS to ensure images render and improve styling
    css_injection = """
    <style>
        img { max-width: 100%; height: auto; display: block; }
        body { font-family: Arial, sans-serif; line-height: 1.6; margin: 20px; }
    </style>
    """
    
    # Inject CSS before </head> or at the start if no head tag
    if '</head>' in html_content:
        html_content = html_content.replace('</head>', f'{css_injection}</head>')
    else:
        html_content = css_injection + html_content
    
    # Write cleaned HTML to a temp file
    temp_html = html_abs.replace('.html', '_cleaned.html')
    with open(temp_html, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Convert temp HTML to file:// URL
    html_url = f"file://{temp_html}"

    # Chrome headless command with no headers/footers
    cmd = [
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless=new',
        '--disable-gpu',
        '--no-sandbox',
        '--virtual-time-budget=10000',
        f'--print-to-pdf={pdf_abs}',
        '--print-to-pdf-no-header',
        '--no-pdf-header-footer',
        html_url
    ]

    subprocess.run(cmd, check=True)
    
    # Clean up temp file
    if os.path.exists(temp_html):
        os.remove(temp_html)
    
    print(f"✅ PDF created at: {pdf_abs}")


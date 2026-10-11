"""Render a saved PDF and record geometric/font checks; visual review remains separate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import pdfplumber
from PIL import Image, ImageDraw


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--log', type=Path, required=True)
    args = parser.parse_args(); out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    assert not (out/'qa-preflight.json').exists(), 'Fresh preflight generation'
    log = args.log.read_text()
    assert not any(x in log.lower() for x in ('overfull', 'undefined', 'error:', 'missing \\endgroup'))
    inventory = []
    with pdfplumber.open(args.pdf) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            words = page.extract_words(); text = page.extract_text() or ''
            assert all(w['x0'] >= -.5 and w['top'] >= -.5 and
                       w['x1'] <= page.width+.5 and w['bottom'] <= page.height+.5 for w in words)
            inventory.append({'page': i, 'words': len(words),
                              'has_tail_table': 'CVaR difference' in text,
                              'has_benefit_table': 'ordinary-benefit allowance' in text,
                              'has_references_heading': '\nReferences\n' in '\n'+text+'\n'})
        extracted = '\n\n'.join(page.extract_text() or '' for page in pdf.pages)
    (out/'extracted.txt').write_text(extracted)
    fonts = subprocess.check_output(['pdffonts', str(args.pdf)], text=True)
    (out/'fonts.txt').write_text(fonts)
    for row in fonts.splitlines()[2:]:
        columns = row.split()
        assert len(columns) >= 8 and columns[-5] == 'yes', ('Unembedded font', row)
    subprocess.run(['pdftoppm', '-r', '90', '-png', str(args.pdf), str(out/'page')], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    pages = sorted(out.glob('page-*.png'), key=lambda p: int(p.stem.split('-')[-1]))
    assert len(pages) == len(inventory)
    for offset in range(0, len(pages), 9):
        sheet = Image.new('RGB', (3*350, 3*500), 'white'); draw = ImageDraw.Draw(sheet)
        for j, path in enumerate(pages[offset:offset+9]):
            with Image.open(path) as im:
                im.thumbnail((335, 465)); x=(j%3)*350+7; y=(j//3)*500+25
                sheet.paste(im, (x,y)); draw.text((x,y-18), f'Page {offset+j+1}', fill='black')
        sheet.save(out/f'contact-{offset//9+1}.png')
    record = {'status': 'compiled_rendered_geometric_checks_passed_visual_review_pending',
              'pdf': str(args.pdf.resolve()), 'pdf_sha256': sha(args.pdf), 'pages': len(pages),
              'log_sha256': sha(args.log), 'renderer_sha256': sha(Path(__file__)),
              'all_extracted_word_bounds_within_page': True, 'all_fonts_embedded': True,
              'font_unicode_limitations': [row for row in fonts.splitlines()[2:] if row.split()[-3] != 'yes'],
              'page_inventory': inventory,
              'render_hashes': {p.name: sha(p) for p in out.iterdir() if p.suffix == '.png'},
              'scope': 'saved development artifact; neither experiment completion nor journal acceptance'}
    (out/'qa-preflight.json').write_text(json.dumps(record, indent=2)+'\n')
    print(f'Rendered {len(pages)} pages; fonts/bounds pass, visual review pending.', flush=True)


if __name__ == '__main__':
    main()

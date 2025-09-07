#!/usr/bin/env python3
"""
Script to convert roguelike map generation reports to Jekyll blog posts.

Usage:
    python scripts/generate_jekyll_posts.py [report_html_path] [--output-dir docs]
    
If no report path is provided, it will process data/report.html by default.
"""

import os
import re
import shutil
import argparse
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup


def extract_report_metadata(soup):
    """Extract metadata from the HTML report."""
    metadata = {}
    
    # Extract title
    title_tag = soup.find('title')
    metadata['title'] = title_tag.get_text() if title_tag else "Roguelike Map Generation Report"
    
    # Extract generation date
    date_paragraph = soup.find('p', style=lambda x: x and 'text-align: center' in x and 'color: #7f8c8d' in x)
    if date_paragraph:
        date_text = date_paragraph.get_text()
        match = re.search(r'Generated on (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', date_text)
        if match:
            metadata['generation_date'] = match.group(1)
            # Parse the date to create a Jekyll-friendly filename date
            try:
                dt = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                metadata['jekyll_date'] = dt.strftime('%Y-%m-%d')
                metadata['post_date'] = dt
            except ValueError:
                metadata['jekyll_date'] = datetime.now().strftime('%Y-%m-%d')
                metadata['post_date'] = datetime.now()
    else:
        # Fallback to current date
        metadata['jekyll_date'] = datetime.now().strftime('%Y-%m-%d')
        metadata['post_date'] = datetime.now()
        metadata['generation_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Extract summary statistics
    summary_cards = soup.find_all('div', class_='summary-card')
    for card in summary_cards:
        h3 = card.find('h3')
        value_div = card.find('div', class_='value')
        if h3 and value_div:
            label = h3.get_text().strip()
            value = value_div.get_text().strip()
            
            if label == 'Total Maps':
                metadata['total_maps'] = int(value) if value.isdigit() else None
            elif label == 'Verification Score':
                score_match = re.search(r'(\d+\.?\d*)', value)
                if score_match:
                    metadata['avg_score'] = float(score_match.group(1))
            elif label == 'Avg Gen Time':
                metadata['avg_gen_time'] = value
    
    return metadata


def process_html_content(soup, output_dir):
    """Process the HTML content and copy images to Jekyll assets."""
    assets_dir = Path(output_dir) / 'assets' / 'images'
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all img tags and update their src paths
    img_tags = soup.find_all('img')
    for img in img_tags:
        src = img.get('src')
        if src and src.startswith('renders/'):
            # Copy image to Jekyll assets
            original_path = Path('data') / src
            if original_path.exists():
                filename = original_path.name
                dest_path = assets_dir / filename
                shutil.copy2(original_path, dest_path)
                
                # Update src to Jekyll asset path
                img['src'] = f"{{{{ '/assets/images/{filename}' | relative_url }}}}"
    
    # Remove the outer html/body structure, keep only the content inside .container
    container = soup.find('div', class_='container')
    if container:
        # Remove the main title as it will be handled by Jekyll layout
        main_title = container.find('h1')
        if main_title:
            main_title.decompose()
        
        return str(container)
    else:
        # Fallback: return body content
        body = soup.find('body')
        return str(body) if body else str(soup)


def create_jekyll_post(report_path, output_dir='docs'):
    """Convert HTML report to Jekyll post."""
    report_path = Path(report_path)
    output_dir = Path(output_dir)
    
    if not report_path.exists():
        raise FileNotFoundError(f"Report file not found: {report_path}")
    
    # Read and parse HTML
    with open(report_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract metadata
    metadata = extract_report_metadata(soup)
    
    # Process HTML content
    processed_content = process_html_content(soup, output_dir)
    
    # Create Jekyll post filename
    post_filename = f"{metadata['jekyll_date']}-map-generation-report.md"
    posts_dir = output_dir / '_posts'
    posts_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate front matter
    front_matter = [
        '---',
        'layout: report',
        f'title: "Map Generation Report - {metadata["jekyll_date"]}"',
        f'date: {metadata["post_date"].strftime("%Y-%m-%d %H:%M:%S %z") if hasattr(metadata["post_date"], "strftime") else metadata["jekyll_date"]}',
        f'generation_date: "{metadata["generation_date"]}"',
    ]
    
    if metadata.get('total_maps'):
        front_matter.append(f'total_maps: {metadata["total_maps"]}')
    if metadata.get('avg_score'):
        front_matter.append(f'avg_score: {metadata["avg_score"]}')
    if metadata.get('avg_gen_time'):
        front_matter.append(f'avg_gen_time: "{metadata["avg_gen_time"]}"')
    
    front_matter.extend([
        'categories: [reports]',
        'tags: [roguelike, procedural-generation, ai]',
        '---',
        ''
    ])
    
    # Write Jekyll post
    post_path = posts_dir / post_filename
    with open(post_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(front_matter))
        f.write(processed_content)
    
    print(f"✅ Created Jekyll post: {post_path}")
    print(f"📊 Report metadata: {metadata['total_maps']} maps, avg score {metadata.get('avg_score', 'N/A')}")
    return post_path


def main():
    parser = argparse.ArgumentParser(description='Convert roguelike reports to Jekyll posts')
    parser.add_argument('report_path', nargs='?', default='data/report.html',
                       help='Path to HTML report file (default: data/report.html)')
    parser.add_argument('--output-dir', default='docs',
                       help='Output directory for Jekyll files (default: docs)')
    
    args = parser.parse_args()
    
    try:
        create_jekyll_post(args.report_path, args.output_dir)
        print("\n🎉 Successfully converted report to Jekyll post!")
        print(f"📁 Check the {args.output_dir}/_posts/ directory")
        print(f"🖼️  Images copied to {args.output_dir}/assets/images/")
        print("\n💡 Next steps:")
        print("   1. Enable GitHub Pages in repository settings")
        print("   2. Set source to 'Deploy from a branch: docs'")
        print("   3. Your blog will be available at: https://username.github.io/rogue/")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
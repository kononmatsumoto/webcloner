import os
import re
from typing import Dict
from anthropic import Anthropic
from anthropic.types import TextBlock
from dotenv import load_dotenv

# Load environment variables - simple approach
load_dotenv()


class LLMService:
    def __init__(self):
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
        if len(api_key) < 50:
            raise ValueError(f"ANTHROPIC_API_KEY appears to be invalid (length: {len(api_key)})")
        self.client = Anthropic(api_key=api_key)
    
    async def generate_html_clone(self, scraped_data: dict) -> str:
        """Generate HTML clone using Anthropic Claude with enhanced dynamic capabilities"""
        try:
            # Build simple but effective system prompt
            system_prompt = """You are an expert web developer who creates pixel-perfect HTML clones.

CRITICAL RULES:
1. Generate EVERY single item provided in the data - NO EXCEPTIONS
2. Never use "..." or truncation phrases
3. Never add explanatory notes about implementation
4. Count items as you generate them: 1, 2, 3... up to the final number
5. Use real URLs and data from the scraped content

For Hacker News specifically:
- Orange header (#ff6600) with proper navigation
- Table layout with proper styling
- Each story has: rank, upvote arrow, title link, score, author, time
- Generate ALL stories individually

OUTPUT: Complete HTML with inline CSS. No explanations."""

            # Build focused user prompt
            user_prompt = self._build_focused_prompt(scraped_data)
            
            # Generate HTML using Claude
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8192,
                temperature=0.05,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            
            # Extract content from response
            content_block = message.content[0]
            if isinstance(content_block, TextBlock):
                html_content = content_block.text
            else:
                html_content = str(content_block)
            
            return self._clean_html_output(html_content)
            
        except Exception as e:
            raise Exception(f"Failed to generate HTML clone: {str(e)}")
    
    def _build_focused_prompt(self, scraped_data: Dict) -> str:
        """Build focused prompt that works reliably"""
        
        url = scraped_data.get('url', '').lower()
        data = scraped_data.get('data', {})
        articles = data.get('articles', [])
        
        if 'news.ycombinator.com' in url and articles:
            return self._build_hacker_news_simple_prompt(articles)
        else:
            return self._build_generic_simple_prompt(scraped_data)
    
    def _build_hacker_news_simple_prompt(self, articles: list) -> str:
        """Build simple but effective Hacker News prompt"""
        
        prompt_parts = [
            f" ABSOLUTE REQUIREMENT: Generate EVERY SINGLE ONE of the {len(articles)} stories below",
            f" COUNT AS YOU GO: 1, 2, 3, 4, 5... all the way to {len(articles)}",
            f" STOP ONLY AFTER GENERATING STORY #{len(articles)} - NOT BEFORE",
            f" NO SHORTCUTS, NO ELLIPSIS (...), NO 'CONTINUING WITH SAME PATTERN'",
            "",
            "STEP-BY-STEP GENERATION:",
            "1. Create orange header (#ff6600) with Hacker News logo and nav",
            "2. Create table structure",
            "3. Generate row 1, then row 2, then row 3... until row " + str(len(articles)),
            "4. Each row: rank, upvote arrow, title link, score, author, time",
            "5. Close table and HTML properly",
            "",
            f"ALL {len(articles)} STORIES TO GENERATE (in this exact order):"
        ]
        
        # Add ALL articles in compact format for generation
        for i, article in enumerate(articles, 1):
            if article and article.get('title'):
                title = article.get('title', '').replace('"', "'")
                href = article.get('href', '#')
                score = article.get('score', '0 points')
                author = article.get('author', 'user')
                time_ago = article.get('time', 'now')
                
                prompt_parts.append(
                    f"{i}. {title} | {href} | {score} by {author} {time_ago}"
                )
        
        prompt_parts.extend([
            "",
            f" GENERATION INSTRUCTIONS:",
            f"1. Start with the orange header (#ff6600)",
            f"2. Create table opening tags",
            f"3. Generate row 1, then row 2, then row 3... continue until row {len(articles)}",
            f"4. DO NOT STOP until you reach story #{len(articles)}",
            f"5. DO NOT use ellipsis (...) or 'continuing with same pattern'",
            f"6. Each row: rank, upvote triangle, title link, score/author/time",
            "",
            f"FORMAT FOR EACH ROW:",
            f"<tr><td>1.</td><td>▲</td><td><a href='URL'>TITLE</a><br>SCORE by AUTHOR TIME</td></tr>",
            "",
            f"DO NOT STOP UNTIL YOU HAVE GENERATED ALL {len(articles)} ROWS"
        ])
        
        return "\n".join(prompt_parts)
    
    def _build_generic_simple_prompt(self, scraped_data: Dict) -> str:
        """Build simple prompt for general websites"""
        
        url = scraped_data.get('url', '').lower()
        data = scraped_data.get('data', {})
        articles = data.get('articles', [])
        
        prompt_parts = [
            f"Generate complete HTML clone of {url}",
            "",
            "CRITICAL RULES: 1. Generate EVERY single item provided in the data - NO EXCEPTIONS",
            "2. Never use '...' or truncation phrases",
            "3. Never add explanatory notes about implementation",
            "4. Count items as you generate them: 1, 2, 3... up to the final number",
            "5. Include ALL images using their actual URLs for proper loading",
            "6. Include ALL text content using the exact text from the original website",
            "",
            "OUTPUT: Complete HTML with inline CSS. No explanations.",
            ""
        ]
        
        # Add text content first - this is crucial for the website to have actual content
        text_content = data.get('textContent', {})
        if text_content:
            prompt_parts.extend([
                " ACTUAL WEBSITE TEXT CONTENT (MUST INCLUDE ALL):",
                ""
            ])
            
            # Add navigation text
            nav_text = text_content.get('navigationText', [])
            if nav_text:
                prompt_parts.append(f"- NAVIGATION TEXT ({len(nav_text)} items):")
                for i, nav in enumerate(nav_text[:15], 1):  # Show first 15 nav items
                    text = nav.get('text', '').strip()
                    href = nav.get('href', '#')
                    if text:
                        prompt_parts.append(f"  {i}. \"{text}\" → {href}")
                prompt_parts.append("  → Include ALL navigation links with exact text")
                prompt_parts.append("")
            
            # Add hero/banner content
            hero_content = text_content.get('heroContent', [])
            if hero_content:
                prompt_parts.append(f"- HERO/BANNER CONTENT ({len(hero_content)} sections):")
                for i, hero in enumerate(hero_content[:5], 1):
                    title = hero.get('title', '').strip()
                    subtitle = hero.get('subtitle', '').strip()
                    cta_texts = hero.get('ctaText', [])
                    if title:
                        prompt_parts.append(f"  {i}. Title: \"{title}\"")
                    if subtitle:
                        prompt_parts.append(f"     Subtitle: \"{subtitle}\"")
                    if cta_texts:
                        prompt_parts.append(f"     CTAs: {', '.join([f'\"{text}\"' for text in cta_texts])}")
                prompt_parts.append("  → Create prominent hero sections with large text")
                prompt_parts.append("")
            
            # Add product content
            product_content = text_content.get('productContent', [])
            if product_content:
                prompt_parts.append(f"- PRODUCT CONTENT ({len(product_content)} products):")
                for i, product in enumerate(product_content[:8], 1):
                    title = product.get('title', '').strip()
                    description = product.get('description', '').strip()
                    price = product.get('price', '').strip()
                    if title:
                        prompt_parts.append(f"  {i}. \"{title}\"")
                    if description and len(description) < 100:
                        prompt_parts.append(f"     Description: \"{description}\"")
                    if price:
                        prompt_parts.append(f"     Price: \"{price}\"")
                prompt_parts.append("  → Create product cards with all text content")
                prompt_parts.append("")
            
            # Add section content
            section_content = text_content.get('sectionContent', [])
            if section_content:
                prompt_parts.append(f"- SECTION CONTENT ({len(section_content)} sections):")
                for i, section in enumerate(section_content[:10], 1):
                    heading = section.get('heading', '').strip()
                    content = section.get('content', '').strip()
                    if heading:
                        prompt_parts.append(f"  {i}. Heading: \"{heading}\"")
                    if content and len(content) < 200:
                        prompt_parts.append(f"     Content: \"{content}\"")
                prompt_parts.append("  → Create sections with headings and content")
                prompt_parts.append("")
            
            # Add button texts
            button_texts = text_content.get('buttonTexts', [])
            if button_texts:
                prompt_parts.append(f"- BUTTON TEXT ({len(button_texts)} buttons):")
                for i, btn in enumerate(button_texts[:10], 1):
                    text = btn.get('text', '').strip()
                    btn_type = btn.get('type', 'button')
                    if text:
                        prompt_parts.append(f"  {i}. \"{text}\" ({btn_type})")
                prompt_parts.append("  → Create buttons with exact text and proper styling")
                prompt_parts.append("")
            
            # Add all other text from the website
            all_text = text_content.get('allText', [])
            if all_text:
                # Filter and group text by importance
                headings = [t for t in all_text if t.get('tagName', '').startswith('h') and len(t.get('text', '').strip()) > 0]
                paragraphs = [t for t in all_text if t.get('tagName') == 'p' and len(t.get('text', '').strip()) > 5]
                links = [t for t in all_text if t.get('tagName') == 'a' and len(t.get('text', '').strip()) > 0]
                
                if headings:
                    prompt_parts.append(f"- HEADINGS ({len(headings)} items):")
                    for i, heading in enumerate(headings[:15], 1):
                        tag = heading.get('tagName', 'h1')
                        text = heading.get('text', '').strip()
                        if text and len(text) < 100:
                            prompt_parts.append(f"  {i}. <{tag}>\"{text}\"</{tag}>")
                    prompt_parts.append("")
                
                if paragraphs:
                    prompt_parts.append(f"- PARAGRAPH TEXT ({len(paragraphs)} items):")
                    for i, para in enumerate(paragraphs[:12], 1):
                        text = para.get('text', '').strip()
                        if text and len(text) < 150:
                            prompt_parts.append(f"  {i}. \"{text}\"")
                    prompt_parts.append("")
                
                if links:
                    prompt_parts.append(f"- LINK TEXT ({len(links)} items):")
                    for i, link in enumerate(links[:12], 1):
                        text = link.get('text', '').strip()
                        if text and len(text) < 50:
                            prompt_parts.append(f"  {i}. \"{text}\"")
                    prompt_parts.append("")
            
            prompt_parts.extend([
                " CRITICAL TEXT CONTENT RULES:",
                "- Include ALL the text content shown above - EVERY SINGLE ITEM",
                "- Use the EXACT text from the original website",
                "- Do NOT use placeholder text like 'Lorem ipsum' or generic content",
                "- Maintain the original text hierarchy and structure",
                "- Ensure all buttons, links, and navigation use the actual text",
                ""
            ])
        
        # Add comprehensive image information
        images = data.get('images', [])
        background_images = data.get('backgroundImages', [])
        logo_images = data.get('logoImages', [])
        
        if images or background_images or logo_images:
            prompt_parts.extend([
                " IMAGES TO INCLUDE (USE EXACT URLS):",
            ])
            
            if logo_images:
                prompt_parts.append(f"- LOGOS/BRAND ({len(logo_images)} items):")
                for i, logo in enumerate(logo_images[:5], 1):  # Show first 5 logos
                    src = logo.get('src', '')
                    alt = logo.get('alt', f'Logo {i}')
                    if src:
                        prompt_parts.append(f"  {i}. {alt}: {src}")
                prompt_parts.append("  → Place in navigation/header areas")
                prompt_parts.append("")
            
            if images:
                prompt_parts.append(f"- CONTENT IMAGES ({len(images)} items):")
                for i, img in enumerate(images[:30], 1):  # Show up to 30 images
                    src = img.get('src', '')
                    alt = img.get('alt', f'Image {i}')
                    width = img.get('width', '')
                    height = img.get('height', '')
                    if src:
                        size_info = f" ({width}x{height})" if width and height else ""
                        prompt_parts.append(f"  {i}. {alt}{size_info}: {src}")
                prompt_parts.append("  → Include ALL with exact dimensions and alt text")
                prompt_parts.append("")
            
            if background_images:
                # Limit to 8 high-quality images for better LLM compliance
                bg_subset = background_images[:8]
                prompt_parts.append(f" BACKGROUND IMAGES IMPLEMENTATION ({len(bg_subset)} required sections):")
                prompt_parts.append("")
                
                for i, bg in enumerate(bg_subset, 1):
                    bg_img = bg.get('backgroundImage', '')
                    if bg_img:
                        prompt_parts.append(f"SECTION {i} TEMPLATE (MANDATORY):")
                        prompt_parts.append(f"  CSS: .section-{i} {{ background-image: url('{bg_img}'); background-size: cover; background-position: center; }}")
                        prompt_parts.append(f"  HTML: <section class='section-{i}'><div class='content'><h2>Section {i}</h2><p>Content here</p></div></section>")
                        prompt_parts.append("")
                
                prompt_parts.append(f" CRITICAL: Generate exactly {len(bg_subset)} sections using the templates above!")
                prompt_parts.append("")
            
            # Update critical rules to use subset
            if background_images:
                bg_subset = background_images[:8]  # Use same subset as above
                prompt_parts.extend([
                    " CRITICAL IMAGE IMPLEMENTATION RULES:",
                    f"- MUST implement exactly {len(bg_subset)} sections as shown in templates above",
                    f"- Copy the exact CSS and HTML structures provided for each section",
                    f"- Each section must use the exact background-image URL specified",
                    "- NO modifications to the template structure allowed",
                    "- NO placeholder images - use the provided URLs exactly",
                    f"- Final result must contain {len(bg_subset)} 'background-image:' declarations",
                    "- Include navigation and other content around these sections",
                    ""
                ])
        
        # Add product cards information
        product_cards = data.get('productCards', [])
        if product_cards:
            prompt_parts.extend([
                f" PRODUCT CARDS ({len(product_cards)} found):",
            ])
            for i, card in enumerate(product_cards[:6], 1):  # Show first 6 product cards
                title = card.get('title', f'Product {i}')
                image = card.get('image', '')
                price = card.get('price', '')
                description = card.get('description', '')[:50] + '...' if card.get('description') else ''
                
                card_info = f"  {i}. {title}"
                if price:
                    card_info += f" - {price}"
                if image:
                    card_info += f" [Image: {image}]"
                if description:
                    card_info += f" ({description})"
                
                prompt_parts.append(card_info)
            
            prompt_parts.extend([
                "  → Create modern card layouts with hover effects",
                "  → Include proper spacing, shadows, and clean typography",
                "  → Make cards responsive with rounded corners",
                ""
            ])
        
        # Add divider information
        dividers = data.get('dividers', [])
        if dividers:
            prompt_parts.extend([
                f" SECTION DIVIDERS ({len(dividers)} found):",
            ])
            for i, div in enumerate(dividers[:3], 1):  # Show first 3 dividers
                tag = div.get('tagName', 'hr')
                className = div.get('className', '')
                border_style = div.get('computedStyle', {}).get('borderTop', '') or div.get('computedStyle', {}).get('borderBottom', '')
                
                div_info = f"  {i}. <{tag}>"
                if className:
                    div_info += f" class='{className}'"
                if border_style and border_style != 'none':
                    div_info += f" [Style: {border_style}]"
                
                prompt_parts.append(div_info)
            
            prompt_parts.extend([
                "  → Add subtle divider lines between sections",
                "  → Use proper margin/padding for visual separation",
                "  → Match original styling and opacity",
                ""
            ])
        
        if articles:
            prompt_parts.extend([
                f"CONTENT DATA ({len(articles)} items - GENERATE ALL):"
            ])
            
            for i, article in enumerate(articles, 1):
                if article and article.get('title'):
                    prompt_parts.append(f"{i}. {article.get('title', '')} - {article.get('href', '')}")
            
            prompt_parts.extend([
                "",
                f"CRITICAL COMPLETION REQUIREMENTS: GENERATE ALL {len(articles)} ITEMS - NO EXCEPTIONS",
                f"COUNT YOUR OUTPUT: Ensure you have exactly {len(articles)} items",
                f"START WITH ITEM 1 and END WITH ITEM {len(articles)}",
                "- DO NOT use '...' or 'remaining items' phrases",
                "- DO NOT truncate or summarize content",
                "- Use REAL URLs from scraped data (not placeholder links)",
                "- Complete the HTML fully"
            ])
        
        # Add final verification for images
        if background_images:
            bg_subset = background_images[:8]  # Use same subset
            prompt_parts.extend([
                "",
                " FINAL VERIFICATION CHECKLIST:",
                f"□ Implemented exactly {len(bg_subset)} sections using the provided templates",
                f"□ Created exactly {len(bg_subset)} CSS background-image declarations",
                f"□ Each section has class .section-1 through .section-{len(bg_subset)}",
                f"□ Used all {len(bg_subset)} exact image URLs provided in templates",
                "□ Each section contains the required content structure",
                "□ Navigation and other elements are properly styled",
                "",
                " DO NOT SUBMIT until ALL checkboxes above are verified!"
            ])
        
        return "\n".join(prompt_parts)
    
    def _detect_website_type(self, url: str, data: Dict) -> str:
        """Intelligently detect website type based on URL and content"""
        
        # News and forum sites
        if any(domain in url for domain in ['news.ycombinator', 'reddit.com', 'lobste.rs', 'slashdot']):
            return "News/Forum Site"
        
        # Documentation sites
        if any(domain in url for domain in ['docs.', 'documentation', 'api.', 'developer.', 'guides']):
            return "Documentation"
        
        # E-commerce indicators
        if any(domain in url for domain in ['shop', 'store', 'amazon', 'ebay', 'product']):
            return "E-commerce"
        
        # Blog indicators
        if any(domain in url for domain in ['blog', 'medium.com', 'wordpress', 'ghost']):
            return "Blog"
        
        # Content analysis for type detection
        articles = data.get('articles', [])
        if articles and len(articles) > 10:
            # Check if articles have forum/news characteristics
            sample_article = articles[0] if articles else {}
            if sample_article.get('score') or sample_article.get('author'):
                return "News/Forum Site"
        
        return "General Website"
    
    def _build_news_requirements(self, url: str, articles: list) -> list:
        """Build requirements for news/forum sites like Hacker News"""
        requirements = []
        
        if 'news.ycombinator.com' in url:
            requirements.extend([
                " HACKER NEWS MANDATORY REQUIREMENTS - NO EXCEPTIONS:",
                "- Orange header (#ff6600) with 'Hacker News' logo and navigation",
                "- Navigation: new | past | comments | ask | show | jobs | submit | login",
                "- Table-based layout with alternating row colors",
                "- Each story has: rank number, title link, domain, score, author, time, comments",
                "- Upvote triangles (▲) next to each story",
                "- Monospace font for metadata (Arial/Helvetica for content)",
                ""
            ])
        else:
            requirements.extend([
                "NEWS/FORUM SITE REQUIREMENTS:",
                "- Header with site branding and navigation",
                "- Story/post listing with voting system",
                "- Each item shows: title, author, score, time, comments",
                "- Clean, readable typography optimized for content consumption",
                ""
            ])
        
        if articles:
            requirements.extend([
                f" CRITICAL CONTENT GENERATION ({len(articles)} items):",
                f"YOU MUST GENERATE EXACTLY {len(articles)} COMPLETE HTML ITEMS",
                f"NO SHORTCUTS, NO COMMENTS, NO TRUNCATION ALLOWED",
                "  Generate every single item below - MANDATORY COMPLIANCE:",
                ""
            ])
            
            # Show ALL articles in compact format to ensure they're all generated
            for i, article in enumerate(articles):
                if article and article.get('title'):
                    compact = f"ITEM {i+1}: {article['title']}"
                    if article.get('href'):
                        compact += f" → {article['href']}"
                    if article.get('score') and article.get('author'):
                        compact += f" [{article['score']} pts by {article.get('author', 'user')}]"
                    if article.get('time'):
                        compact += f" {article['time']}"
                    requirements.append(compact)
            
            requirements.extend([
                "",
                f" FINAL REMINDER: You MUST generate {len(articles)} separate tr.athing rows",
                f"Count as you go: 1, 2, 3... up to {len(articles)}",
                "Each must have: rank number, upvote arrow, title link, subtext with score/author/time",
                "Use the EXACT data shown above for each item",
                "DO NOT STOP until you reach the final item",
                ""
            ])
        
        return requirements
    
    def _build_blog_requirements(self, data: Dict) -> list:
        """Build requirements for blog sites"""
        return [
            "BLOG SITE REQUIREMENTS:",
            "- Clean, content-focused design with good typography",
            "- Article cards or list layout with featured images",
            "- Author information, publish dates, read time estimates",
            "- Categories/tags for organization",
            "- Search functionality and archive navigation",
            "- Social sharing buttons and comment sections",
            ""
        ]
    
    def _build_ecommerce_requirements(self, data: Dict) -> list:
        """Build requirements for e-commerce sites"""
        return [
            "E-COMMERCE SITE REQUIREMENTS:",
            "- Product grid layout with high-quality images",
            "- Price display, ratings, reviews, and 'Add to Cart' buttons",
            "- Category navigation and filtering options",
            "- Search bar prominently displayed",
            "- Shopping cart icon with item count",
            "- Trust indicators (secure checkout, return policy)",
            ""
        ]
    
    def _build_docs_requirements(self, data: Dict) -> list:
        """Build requirements for documentation sites"""
        return [
            "DOCUMENTATION SITE REQUIREMENTS:",
            "- Sidebar navigation with hierarchical structure",
            "- Code syntax highlighting with copy buttons",
            "- Search functionality with autocomplete",
            "- Breadcrumb navigation",
            "- 'Edit on GitHub' links and contribution info",
            "- Mobile-responsive sidebar that collapses",
            ""
        ]
    
    def _build_generic_requirements(self, data: Dict) -> list:
        """Build requirements for general websites"""
        requirements = []
        
        # Enhanced Navigation structure with layout details
        navigation = data.get('navigation', {})
        header_links = navigation.get('headerLinks', [])
        header_structure = navigation.get('headerStructure', {})
        
        if header_links or header_structure:
            requirements.append("APPLE-STYLE NAVIGATION REQUIREMENTS:")
            requirements.append("- CRITICAL: Use Apple's signature navigation design patterns with EXACT alignment")
            requirements.append("- Navigation background: Dark (#000000) with transparency backdrop-filter: saturate(180%) blur(20px);")
            requirements.append("- Navigation text color: Light gray/white (#f5f5f7, #d2d2d7)")
            requirements.append("- Navigation height: EXACTLY 44px (Apple standard) with no extra padding")
            requirements.append("- Font: Use Apple system fonts (-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', Helvetica, Arial, sans-serif)")
            requirements.append("")
            requirements.append("CRITICAL NAVIGATION LAYOUT & ALIGNMENT:")
            requirements.append("- Container: width: 100%, max-width: 980px, margin: 0 auto (centered layout)")
            requirements.append("- Flexbox layout: display: flex, justify-content: space-between, align-items: center")
            requirements.append("- Left side: Apple logo (far left with 22px left margin)")
            requirements.append("- Center: Navigation menu items with equal spacing")
            requirements.append("- Right side: Search icon and shopping bag icon")
            requirements.append("- Logo dimensions: height: 20px, width: auto, margin-right: 20px")
            requirements.append("- Menu items: font-size: 12px, padding: 0 8px, height: 44px, line-height: 44px")
            requirements.append("- Item spacing: margin: 0 4px between items, no extra padding")
            requirements.append("- Menu alignment: center menu items evenly between logo and icons")
            requirements.append("- Icons on right: search and bag icons, 20px padding each side")
            requirements.append("")
            requirements.append("NAVIGATION HTML STRUCTURE REQUIREMENTS:")
            requirements.append("- Use semantic <nav> element with proper ARIA labels")
            requirements.append("- Logo in <div class='nav-brand'> on the left")
            requirements.append("- Menu in <ul class='nav-menu'> in the center")
            requirements.append("- Icons in <div class='nav-icons'> on the right")
            requirements.append("- HTML Structure Example:")
            requirements.append("  <nav><div class='nav-container'>")
            requirements.append("    <div class='nav-brand'><a href='/'><img src='[apple-logo]' alt='Apple' /></a></div>")
            requirements.append("    <ul class='nav-menu'>")
            requirements.append("      <li><a href='/store/'>Store</a></li>")
            requirements.append("      <li><a href='/mac/'>Mac</a></li>")
            requirements.append("      <!-- all navigation items -->")
            requirements.append("    </ul>")
            requirements.append("    <div class='nav-icons'>")
            requirements.append("      <a href='/search/'><svg>search icon</svg></a>")
            requirements.append("      <a href='/bag/'><svg>bag icon</svg></a>")
            requirements.append("    </div>")
            requirements.append("  </div></nav>")
            requirements.append("- Ensure proper focus states and keyboard navigation")
            requirements.append("- Position: fixed, top: 0, z-index: 9999 for sticky behavior")
            requirements.append("")
            
            # Header structure information
            if header_structure:
                header_element = header_structure.get('headerElement', 'header')
                header_style = header_structure.get('headerStyle', {})
                logo_position = header_structure.get('logoPosition', 'left')
                is_sticky = header_structure.get('isSticky', False)
                
                requirements.append("NAVIGATION LAYOUT STRUCTURE:")
                requirements.append(f"- Header element: {header_element}")
                if header_style.get('backgroundColor'):
                    requirements.append(f"- Detected background: {header_style.get('backgroundColor')}")
                if header_style.get('height'):
                    requirements.append(f"- Detected height: {header_style.get('height')}")
                
                requirements.extend([
                    f"- Logo position: {logo_position} (ENFORCE left positioning)",
                    f"- Sticky/Fixed: {is_sticky}",
                    "- CRITICAL: Use 3-section flexbox layout:",
                    "  1. LEFT: Apple logo (fixed width, no shrinking)",
                    "  2. CENTER: Navigation menu items (flex-grow, centered)",
                    "  3. RIGHT: Search/bag icons (fixed width)",
                    "- Container: justify-content: space-between, align-items: center",
                    "- Logo container: flex-shrink: 0, margin-right: auto",
                    "- Menu container: display: flex, gap: 24px, justify-content: center",
                    "- Ensure perfect vertical alignment for all items"
                ])
            
            # Navigation links
            if header_links:
                requirements.append("")
                requirements.append("NAVIGATION LINKS:")
                for link in header_links[:10]:
                    text = link.get('text', '').strip()
                    href = link.get('absoluteHref', link.get('href', ''))
                    if text and href:
                        requirements.append(f"  • {text}: {href}")
                
                requirements.extend([
                    "",
                    "NAVIGATION STYLING RULES:",
                    "- Link color: #f5f5f7 (Apple's light gray)",
                    "- Font size: 14px, font-weight: 400",
                    "- Padding: 8px 12px for each link",
                    "- Hover effect: opacity: 0.8, transition: opacity 0.2s ease",
                    "- Letter spacing: -0.016em (Apple standard)",
                    "- Line height: 1.47 (Apple standard)",
                    "- No text decoration, cursor: pointer",
                    "- Maintain 24px gap between navigation items",
                    "- Ensure links are perfectly centered within their containers"
                ])
            
            requirements.append("")
        
        # Main content
        articles = data.get('articles', [])
        generic_articles = data.get('genericArticles', [])
        
        if articles:
            requirements.append(f"MAIN CONTENT ({len(articles)} items):")
            for i, article in enumerate(articles[:25]):  # Show more items
                if article and article.get('title'):
                    item_line = f"{i+1}. {article['title']}"
                    if article.get('href'):
                        item_line += f" → {article['href']}"
                    requirements.append(item_line)
            requirements.append("")
        elif generic_articles:
            requirements.append(f"ARTICLES/POSTS ({len(generic_articles)} items):")
            for i, article in enumerate(generic_articles[:20]):
                if article and article.get('title'):
                    requirements.append(f"{i+1}. {article['title']}")
                    if article.get('href'):
                        requirements.append(f"   Link: {article['href']}")
            requirements.append("")
        
        return requirements
    
    def _build_design_requirements(self, data: Dict) -> list:
        """Build universal design and layout requirements"""
        requirements = []
        
        # Layout information
        layout = data.get('layout', {})
        if layout:
            requirements.append("LAYOUT STRUCTURE:")
            if layout.get('hasTopNav'):
                requirements.append("- Top navigation bar with brand and menu items")
            if layout.get('hasSidebar'):
                requirements.append("- Sidebar with secondary navigation or content")
            if layout.get('hasMainContent'):
                requirements.append("- Main content area with primary information")
            if layout.get('isResponsive'):
                requirements.append("- Responsive design for mobile and tablet devices")
            
            # Add section and product layout requirements
            requirements.extend([
                "- Use section dividers/lines between content areas",
                "- Create product cards/boxes for featured items",
                "- Maintain proper spacing and visual hierarchy",
                "- Include hover effects and modern styling"
            ])
            requirements.append("")
        
        # Image requirements
        images = data.get('images', [])
        background_images = data.get('backgroundImages', [])
        logo_images = data.get('logoImages', [])
        
        if images or background_images or logo_images:
            requirements.append("IMAGES AND MEDIA:")
            
            # Prioritize logo images first with enhanced Apple logo handling
            if logo_images:
                requirements.append(f"- APPLE LOGO IMPLEMENTATION ({len(logo_images)} found):")
                
                # Find the best Apple logo
                apple_logos = [logo for logo in logo_images if logo.get('isAppleLogo', False)]
                if apple_logos:
                    for logo in apple_logos[:1]:  # Use the first Apple logo found
                        alt_text = logo.get('alt', 'Apple')
                        src_info = logo.get('src', '')
                        parent_context = logo.get('parentElement', '')
                        natural_width = logo.get('naturalDimensions', {}).get('width', 0)
                        natural_height = logo.get('naturalDimensions', {}).get('height', 0)
                        
                        if src_info:
                            requirements.append(f"  • APPLE LOGO: {src_info}")
                            requirements.append(f"  • Alt text: \"{alt_text}\"")
                            requirements.append(f"  • Dimensions: {natural_width}x{natural_height}px")
                            requirements.append(f"  • Context: {parent_context}")
                else:
                    # Fallback to any logo found
                    for logo in logo_images[:2]:
                        alt_text = logo.get('alt', 'Logo')
                        src_info = logo.get('src', '')
                        if src_info:
                            requirements.append(f"  • {alt_text}: {src_info}")
                
                requirements.extend([
                    "",
                    "CRITICAL APPLE LOGO REQUIREMENTS:",
                    "- Use the EXACT Apple logo URL found above - NO substitutions or placeholders",
                    "- Position logo on the FAR LEFT of navigation with proper spacing",
                    "- Set logo height to exactly 20px (Apple's standard)",
                    "- Use width: auto to maintain aspect ratio",
                    "- Apply proper Apple logo styling:",
                    "  • filter: brightness(0) invert(1) for white logo on dark background",
                    "  • OR use original logo if it's already white/transparent",
                    "- Logo container: flex-shrink: 0, margin-right: 20px",
                    "- Make logo clickable: wrap in <a href='/'>",
                    "- Add hover effect: opacity: 0.8 on hover",
                    "- Ensure logo loads correctly and is not broken or showing as text"
                ])
                requirements.append("")
            
            if images:
                requirements.append(f"- CONTENT IMAGES ({len(images)} found):")
                for img in images[:8]:  # Show more images for better coverage
                    alt_text = img.get('alt', 'Image')
                    src_info = img.get('src', '')
                    if src_info:
                        # Extract meaningful filename from URL
                        filename = src_info.split('/')[-1].split('?')[0]
                        requirements.append(f"  • {alt_text or filename}: {src_info}")
                requirements.append("- Include ALL images with exact URLs, alt text, and dimensions")
                requirements.append("")
            
            if background_images:
                requirements.append(f"- BACKGROUND IMAGES ({len(background_images)} found):")
                for bg in background_images[:5]:  # Show more background images
                    element = bg.get('element', 'div')
                    bg_img = bg.get('backgroundImage', '')
                    if bg_img:
                        requirements.append(f"  • {element}: {bg_img}")
                requirements.append("- Apply as CSS background-image property with proper sizing")
                requirements.append("")
            
            requirements.extend([
                "- CRITICAL: Use actual image URLs from scraped data - NO placeholder images",
                "- Include proper image dimensions, alt text, and responsive attributes",
                "- Maintain original image aspect ratios and positioning exactly",
                ""
            ])
        
        # Typography and fonts with Apple-specific enhancements
        fonts = data.get('fonts', {})
        if fonts:
            requirements.append("APPLE TYPOGRAPHY SYSTEM:")
            
            body_font = fonts.get('bodyFont', '')
            has_apple_fonts = fonts.get('hasAppleFonts', False)
            navigation_fonts = fonts.get('navigationFonts', [])
            
            if body_font:
                requirements.append(f"- Detected body font: {body_font}")
            
            if has_apple_fonts:
                requirements.append("- Apple system fonts detected in original")
            
            if navigation_fonts:
                requirements.append("- Navigation typography:")
                for nav in navigation_fonts[:3]:  # Show first 3 nav items
                    font = nav.get('fontFamily', '')
                    size = nav.get('fontSize', '')
                    weight = nav.get('fontWeight', '')
                    spacing = nav.get('letterSpacing', '')
                    text = nav.get('textContent', '')[:20]
                    if font and text:
                        requirements.append(f"  • \"{text}\": {font} ({size}, {weight}, {spacing})")
            
            heading_fonts = fonts.get('headingFonts', [])
            if heading_fonts:
                requirements.append("- Heading typography:")
                for h in heading_fonts[:4]:  # Show sample headings
                    tag = h.get('tag', 'h1')
                    font = h.get('fontFamily', '')
                    size = h.get('fontSize', '')
                    weight = h.get('fontWeight', '')
                    spacing = h.get('letterSpacing', '')
                    content = h.get('textContent', '')[:25]
                    if font and content:
                        requirements.append(f"  • {tag}: {font} ({size}, {weight}, {spacing}) - \"{content}\"")
            
            primary_fonts = fonts.get('primaryFonts', [])
            if primary_fonts:
                requirements.append(f"- Primary fonts detected: {', '.join(primary_fonts[:3])}")
            
            requirements.extend([
                "",
                "FONT IMPLEMENTATION REQUIREMENTS:",
                "- PRIMARY: Use the detected font stack from original website or fallback to system fonts:",
                "  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Icons', 'Helvetica Neue', Helvetica, Arial, sans-serif;",
                "- Navigation text: 14px, font-weight: 400, letter-spacing: -0.016em",
                "- Hero text: Large sizes with proper letter-spacing (-0.022em for 17px+)",
                "- Body text: 17px, font-weight: 400, line-height: 1.47",
                "",
                "SCRAPED TYPOGRAPHY COLOR SYSTEM:",
            ])
            
            # Use scraped colors instead of hardcoded values
            nav_colors = scraped_colors.get('navigation_colors', {})
            body_colors = scraped_colors.get('body_colors', [])
            
            if nav_colors.get('background') or nav_colors.get('text'):
                requirements.append(f"- Navigation background: {nav_colors.get('background', '#ffffff')}")
                requirements.append(f"- Navigation text: {nav_colors.get('text', '#000000')}")
                if nav_colors.get('link_colors'):
                    link_colors = ', '.join(nav_colors['link_colors'][:3])
                    requirements.append(f"- Navigation links: {link_colors}")
            else:
                # Fallback colors if no navigation colors detected
                requirements.append("- Navigation text: #F5F5F7 (fallback light gray)")
                requirements.append("- Navigation background: #1d1d1f (fallback dark)")
            
            # Add body text colors by role
            for color_info in body_colors[:5]:  # Show first 5 color roles
                role = color_info.get('role', 'content')
                color = color_info.get('color', '#000000')
                count = color_info.get('usage_count', 0)
                requirements.append(f"- {role.title()} text: {color} (used {count} times)")
            
            # Add heading colors if available
            heading_colors = scraped_colors.get('heading_colors', [])
            if heading_colors:
                requirements.append("- Heading colors from original:")
                for heading in heading_colors[:3]:  # Show first 3 heading colors
                    level = heading.get('level', 1)
                    color = heading.get('colors', {}).get('textColor', '#000000')
                    text_sample = heading.get('text', '')[:20]
                    requirements.append(f"  • H{level}: {color} (e.g., \"{text_sample}\")")
            
            requirements.extend([
                "",
                "APPLE NAVIGATION CSS REQUIREMENTS:",
                "- Navigation wrapper: background: rgba(0,0,0,0.8); backdrop-filter: saturate(180%) blur(20px);",
                "- Navigation container CSS:",
                "  .nav-container { max-width: 980px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; height: 44px; padding: 0 22px; }",
                "- Logo CSS: .nav-brand img { height: 20px; width: auto; filter: brightness(0) invert(1); }",
                "- Menu CSS: .nav-menu { display: flex; list-style: none; margin: 0; padding: 0; gap: 0; }",
                "- Menu item CSS: .nav-menu li { margin: 0 4px; } .nav-menu a { color: #f5f5f7; text-decoration: none; font-size: 12px; padding: 0 8px; display: block; line-height: 44px; transition: opacity 0.3s; }",
                "- Hover states: .nav-menu a:hover, .nav-brand:hover { opacity: 0.8; }",
                "- Icons CSS: .nav-icons { display: flex; gap: 16px; } .nav-icons svg { width: 20px; height: 20px; fill: #f5f5f7; }",
                "",
                "CRITICAL TYPOGRAPHY RULES:",
                "- Use the EXACT colors scraped from the original website above",
                "- Maintain proper contrast ratios for accessibility",
                "- Apply consistent letter-spacing values from original",
                "- Use proper line-height ratios (1.47 for body, 1.2 for headlines)",
                "- Ensure text renders crisply with -webkit-font-smoothing: antialiased",
                "- Match original font weights and sizes exactly from detected typography"
            ])
            requirements.append("")
        
        # Interactive buttons and CTAs
        buttons = data.get('buttons', [])
        cta_elements = data.get('ctaElements', [])
        text_content = data.get('textContent', {})
        
        # Extract actual colors from scraped data
        scraped_colors = self._extract_color_information(data)
        
        if buttons or cta_elements or text_content:
            requirements.append("INTERACTIVE ELEMENTS & BUTTON DESIGN:")
            
            # Use actual scraped button text and colors
            actual_button_texts = []
            button_color_info = []
            
            # Extract button colors from scraped data
            if text_content.get('buttonColors'):
                for btn_data in text_content['buttonColors'][:10]:
                    btn_text = btn_data.get('text', '').strip()
                    colors = btn_data.get('colors', {})
                    if btn_text:
                        actual_button_texts.append(f"  • \"{btn_text}\"")
                        if colors:
                            button_color_info.append({
                                'text': btn_text,
                                'textColor': colors.get('textColor', '#000000'),
                                'backgroundColor': colors.get('backgroundColor', 'transparent'),
                                'borderColor': colors.get('borderColor', 'transparent')
                            })
            
            # Collect button text from scraped data
            if text_content.get('buttonTexts'):
                for btn_data in text_content['buttonTexts'][:10]:
                    btn_text = btn_data.get('text', '').strip()
                    if btn_text and not any(btn_text in item for item in actual_button_texts):
                        actual_button_texts.append(f"  • \"{btn_text}\"")
            
            # Collect CTA text from scraped elements
            if buttons:
                for btn in buttons[:10]:
                    btn_text = btn.get('text', '').strip()
                    if btn_text and not any(btn_text in item for item in actual_button_texts):
                        actual_button_texts.append(f"  • \"{btn_text}\"")
            
            if cta_elements:
                for cta in cta_elements[:10]:
                    cta_text = cta.get('text', '').strip()
                    if cta_text and not any(cta_text in item for item in actual_button_texts):
                        actual_button_texts.append(f"  • \"{cta_text}\"")
            
            if actual_button_texts:
                requirements.append("ACTUAL BUTTON TEXT FROM WEBSITE:")
                requirements.extend(actual_button_texts[:15])  # Limit to 15 buttons
                requirements.append("")
                
                # Add button color information if available
                if button_color_info:
                    requirements.append("BUTTON COLOR STYLING FROM ORIGINAL:")
                    for btn_info in button_color_info[:5]:  # Show first 5 button color styles
                        text = btn_info.get('text', '')
                        text_color = btn_info.get('textColor', '#000000')
                        bg_color = btn_info.get('backgroundColor', 'transparent')
                        border_color = btn_info.get('borderColor', 'transparent')
                        
                        requirements.append(f"- \"{text}\":")
                        requirements.append(f"  • Text color: {text_color}")
                        requirements.append(f"  • Background: {bg_color}")
                        if border_color != 'transparent':
                            requirements.append(f"  • Border: {border_color}")
                    requirements.append("")
            
            # Use extracted button text for styling requirements
            primary_btn_text = "Learn more"  # Default fallback
            secondary_btn_text = "Buy"      # Default fallback
            primary_btn_colors = None
            secondary_btn_colors = None
            
            # Try to find actual button text and colors from scraped content
            if actual_button_texts:
                for btn_line in actual_button_texts:
                    if '"' in btn_line:
                        btn_text = btn_line.split('"')[1].lower()
                        actual_text = btn_line.split('"')[1]
                        if 'learn' in btn_text or 'more' in btn_text or 'explore' in btn_text:
                            primary_btn_text = actual_text
                            # Find matching color info
                            for btn_info in button_color_info:
                                if btn_info.get('text', '').lower() == actual_text.lower():
                                    primary_btn_colors = btn_info
                                    break
                        elif 'buy' in btn_text or 'shop' in btn_text or 'order' in btn_text:
                            secondary_btn_text = actual_text
                            # Find matching color info
                            for btn_info in button_color_info:
                                if btn_info.get('text', '').lower() == actual_text.lower():
                                    secondary_btn_colors = btn_info
                                    break
            
            # Build button styling requirements using scraped colors when available
            requirements.extend([
                "",
                "BUTTON DESIGN REQUIREMENTS (USING ORIGINAL COLORS):",
            ])
            
            if primary_btn_colors:
                bg_color = primary_btn_colors.get('backgroundColor', '#007AFF')
                text_color = primary_btn_colors.get('textColor', '#ffffff')
                requirements.append(f"- Primary button (\"{primary_btn_text}\"): Background {bg_color} with text color {text_color}")
            else:
                requirements.append(f"- Primary button (\"{primary_btn_text}\"): Blue (#007AFF) with white text (fallback)")
            
            requirements.extend([
                "- Button dimensions: padding: 12px 22px, border-radius: 8px",
                "- Typography: font-weight: 400, font-size: 17px, letter-spacing: -0.022em",
                "- Button font: Use system fonts or match original font family",
                "- Hover effect: Slightly darker shade with smooth transition",
                "- Shadow: subtle drop shadow (0 2px 4px rgba(0,0,0,0.1))",
                "- Active state: transform: scale(0.96) for brief press feedback",
                "- Transition: all properties with 0.2s ease timing",
                "",
            ])
            
            if secondary_btn_colors:
                bg_color = secondary_btn_colors.get('backgroundColor', '#F2F2F7')
                text_color = secondary_btn_colors.get('textColor', '#1D1D1F')
                requirements.append(f"- Secondary button (\"{secondary_btn_text}\"): Background {bg_color} with text color {text_color}")
            else:
                requirements.append(f"- Secondary button (\"{secondary_btn_text}\"): Light background (#F2F2F7) with dark text (#1D1D1F) (fallback)")
            
            requirements.extend([
                "- Same dimensions and transitions as primary buttons",
                "- Hover: Slightly darker background shade",
                "",
                "CTA INTERACTION REQUIREMENTS:",
                "- Make ALL buttons and CTAs fully clickable and interactive",
                "- Ensure buttons have proper cursor: pointer",
                "- Include smooth micro-interactions on hover and click",
                "- Maintain Apple's accessibility standards",
                f"- Use the EXACT button text from the original website: \"{primary_btn_text}\", \"{secondary_btn_text}\", etc.",
                "- Ensure button text is center-aligned and properly sized"
            ])
            requirements.append("")
        
        # Use scraped product content instead of generic placeholders
        product_content = text_content.get('productContent', [])
        hero_content = text_content.get('heroContent', [])
        section_content = text_content.get('sectionContent', [])
        
        if product_content or hero_content or section_content:
            requirements.append("ACTUAL WEBSITE CONTENT TO INCLUDE:")
            
            if hero_content:
                requirements.append("HERO/BANNER CONTENT:")
                for hero in hero_content[:3]:  # Show first 3 hero sections
                    title = hero.get('title', '').strip()
                    subtitle = hero.get('subtitle', '').strip()
                    if title:
                        requirements.append(f"  • Title: \"{title}\"")
                    if subtitle:
                        requirements.append(f"  • Subtitle: \"{subtitle}\"")
                    cta_texts = hero.get('ctaText', [])
                    if cta_texts:
                        requirements.append(f"  • CTA buttons: {', '.join([f'\"{text}\"' for text in cta_texts])}")
                requirements.append("")
            
            if product_content:
                requirements.append("PRODUCT CONTENT:")
                for product in product_content[:5]:  # Show first 5 products
                    title = product.get('title', '').strip()
                    description = product.get('description', '').strip()
                    price = product.get('price', '').strip()
                    if title:
                        requirements.append(f"  • Product: \"{title}\"")
                    if description and len(description) < 100:
                        requirements.append(f"    Description: \"{description}\"")
                    if price:
                        requirements.append(f"    Price: \"{price}\"")
                    button_texts = product.get('buttonText', [])
                    if button_texts:
                        requirements.append(f"    Buttons: {', '.join([f'\"{text}\"' for text in button_texts])}")
                requirements.append("")
            
            if section_content:
                requirements.append("SECTION CONTENT:")
                for section in section_content[:5]:  # Show first 5 sections
                    heading = section.get('heading', '').strip()
                    content = section.get('content', '').strip()
                    if heading:
                        requirements.append(f"  • Section: \"{heading}\"")
                    if content and len(content) < 150:
                        requirements.append(f"    Content: \"{content}\"")
                requirements.append("")
        
        # Use scraped navigation text
        navigation_text = text_content.get('navigationText', [])
        if navigation_text:
            requirements.append("NAVIGATION MENU ITEMS:")
            for nav_item in navigation_text[:12]:  # Show first 12 nav items
                nav_text = nav_item.get('text', '').strip()
                if nav_text:
                    requirements.append(f"  • \"{nav_text}\"")
            requirements.append("")
        
        # Product cards and layout elements
        product_cards = data.get('productCards', [])
        dividers = data.get('dividers', [])
        
        if product_cards or dividers:
            requirements.append("LAYOUT ELEMENTS:")
            
            if product_cards:
                requirements.append(f"- PRODUCT CARDS ({len(product_cards)} found):")
                for card in product_cards[:4]:  # Show first 4 product cards
                    title = card.get('title', 'Product')
                    image = card.get('image', '')
                    if title and image:
                        requirements.append(f"  • {title}: {image}")
                requirements.extend([
                    "- Create modern, clean card layouts with hover effects",
                    "- Include product images, titles, and descriptions",
                    "- Use the EXACT button text from the scraped content for each card",
                    "- Use Apple-style spacing, typography, and card shadows",
                    "- Ensure card buttons are properly styled and clickable"
                ])
            
            if dividers:
                requirements.append(f"- SECTION DIVIDERS ({len(dividers)} found):")
                requirements.extend([
                    "- Add subtle lines/dividers between content sections",
                    "- Use thin, light borders or HR elements",
                    "- Maintain proper spacing and visual hierarchy"
                ])
            
            requirements.append("")
        
        # Color scheme
        colors = data.get('colors', [])
        if colors:
            requirements.append("COLOR PALETTE:")
            requirements.append(f"Primary colors: {', '.join(colors[:6])}")
            requirements.append("")
        
        # Typography from headings
        headings = data.get('headings', [])
        if headings:
            requirements.append("CONTENT HIERARCHY:")
            hierarchy = {}
            for h in headings[:15]:
                level = h.get('level', 1)
                if level not in hierarchy:
                    hierarchy[level] = []
                hierarchy[level].append(h.get('text', '').strip())
            
            for level in sorted(hierarchy.keys()):
                requirements.append(f"H{level}: {', '.join(hierarchy[level][:3])}")
            requirements.append("")
        
        # Footer information
        navigation = data.get('navigation', {})
        footer_links = navigation.get('footerLinks', [])
        if footer_links:
            requirements.append("FOOTER NAVIGATION:")
            for link in footer_links[:8]:
                text = link.get('text', '').strip()
                if text:
                    requirements.append(f"- {text}")
            requirements.append("")
        
        # Modern styling requirements
        requirements.extend([
            "MODERN INTERACTIVE DESIGN REQUIREMENTS:",
            "- Use CSS transitions for smooth hover effects (0.3s ease-in-out)",
            "- Add subtle box-shadows and elevate elements on hover",
            "- Implement proper button states: default, hover, active, focus",
            "- Use modern CSS features: flexbox, grid, css variables",
            "- Include smooth scrolling and proper spacing (use rem/em units)",
            "- Add loading states and micro-interactions where appropriate",
            "- Ensure all interactive elements have visual feedback",
            "- Use consistent border-radius (Apple uses 8px-12px typically)",
            "- Include proper typography scale and consistent spacing system",
            "",
            "NAVIGATION BAR SPECIFIC REQUIREMENTS:",
            "- Create a proper flexbox navigation layout with three sections:",
            "  1. Logo on the LEFT (flex-shrink: 0)",
            "  2. Navigation menu in the CENTER (display: flex, gap: 20px)",
            "  3. Additional items on the RIGHT (if any)",
            "- Use justify-content: space-between on the main nav container",
            "- Ensure logo img has proper constraints: max-height: 32px, width: auto",
            "- Navigation items should have consistent padding: 8px 16px",
            "- Center all items vertically with align-items: center",
            "- Use a fixed or sticky header with proper z-index (z-index: 1000)",
            "- Ensure navigation text is legible and properly spaced",
            "- Apply consistent hover states to all clickable navigation elements",
            ""
        ])
        
        return requirements

    def _extract_color_information(self, data: Dict) -> Dict:
        """Extract comprehensive color information from scraped data"""
        text_content = data.get('textContent', {})
        colors_info = {
            'navigation_colors': {},
            'button_colors': [],
            'heading_colors': [],
            'body_colors': [],
            'background_colors': [],
            'color_palette': []
        }
        
        # Extract navigation colors
        if text_content.get('navigationColors'):
            nav_colors = text_content['navigationColors'][0] if text_content['navigationColors'] else {}
            colors_info['navigation_colors'] = {
                'background': nav_colors.get('backgroundColor', '#ffffff'),
                'text': nav_colors.get('textColor', '#000000'),
                'link_colors': [link.get('color', '#000000') for link in nav_colors.get('linkColors', [])]
            }
        
        # Extract button colors
        if text_content.get('buttonColors'):
            colors_info['button_colors'] = text_content['buttonColors']
        
        # Extract heading colors
        if text_content.get('headingColors'):
            colors_info['heading_colors'] = text_content['headingColors']
        
        # Extract general text colors
        if text_content.get('allText'):
            text_elements = text_content['allText']
            # Group by text role
            role_colors = {}
            for elem in text_elements[:50]:  # Process first 50 text elements
                if elem.get('styles') and elem['styles'].get('color'):
                    role = elem['styles'].get('textRole', 'content')
                    color = elem['styles']['color']
                    if role not in role_colors:
                        role_colors[role] = []
                    role_colors[role].append(color)
            
            # Get most common color for each role
            for role, colors in role_colors.items():
                if colors:
                    # Find most common color
                    color_counts = {}
                    for color in colors:
                        color_counts[color] = color_counts.get(color, 0) + 1
                    most_common = max(color_counts.items(), key=lambda x: x[1])[0]
                    colors_info['body_colors'].append({
                        'role': role,
                        'color': most_common,
                        'usage_count': color_counts[most_common]
                    })
        
        # Extract color palette
        if text_content.get('colorPalette'):
            colors_info['color_palette'] = text_content['colorPalette']
        
        return colors_info

    def _clean_html_output(self, html_content: str) -> str:
        """Clean and validate HTML output with enhanced formatting and aggressive note removal"""
        # Remove any markdown code block markers
        if html_content.startswith('```html'):
            html_content = html_content[7:]
        if html_content.startswith('```'):
            html_content = html_content[3:]
        if html_content.endswith('```'):
            html_content = html_content[:-3]
        
        # AGGRESSIVELY remove any LLM explanatory text or notes
        import re
        
        # Remove notes in square brackets
        html_content = re.sub(r'\[Note:.*?\]', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'\[Continuing.*?\]', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove specific problematic phrases
        problematic_phrases = [
            r'Due to length limits.*?throughout\.\]',
            r'Note: Due to length limits.*?structure throughout\.\]',
            r'\[.*?length limits.*?\]',
            r'I\'ve shown the structure.*?items\.',
            r'The complete implementation.*?data\.',
            r'would include all \d+ items.*?\.',
            r'following the exact same pattern.*?\.',
            r'maintaining consistent styling.*?\.',
            r'Continuing with all \d+ items.*?\.',
            r'For brevity.*?items\.',
            r'<!-- Remaining.*?-->'
        ]
        
        for phrase in problematic_phrases:
            html_content = re.sub(phrase, '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Clean up line by line for more specific filtering
        lines = html_content.split('\n')
        cleaned_lines = []
        in_html = False
        
        for line in lines:
            # Skip any lines that contain explanatory notes
            if any(phrase in line.lower() for phrase in [
                'note:', 'due to length limits', 'i\'ve shown', 'complete implementation',
                'would include all', 'following the exact same pattern', 'maintaining consistent',
                'for brevity', 'remaining items', 'continuing with all', 'items following'
            ]):
                continue
                
            # Start collecting lines when we hit HTML content
            if '<!DOCTYPE' in line or '<html' in line or (in_html and line.strip()):
                in_html = True
                cleaned_lines.append(line)
            elif in_html:
                cleaned_lines.append(line)
            # Skip explanatory text before HTML starts
        
        if cleaned_lines:
            html_content = '\n'.join(cleaned_lines)
        
        # Final cleanup - remove any remaining bracketed content that looks like notes
        html_content = re.sub(r'\[.*?(?:implementation|pattern|styling|brevity|length).*?\]', '', html_content, flags=re.IGNORECASE)
        
        # Ensure we have a complete HTML document
        if not html_content.strip().startswith('<!DOCTYPE') and not html_content.strip().startswith('<html'):
            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cloned Website</title>
    <style>
        body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        * {{ box-sizing: border-box; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""
        
        return html_content.strip() 
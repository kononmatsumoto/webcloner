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

 CRITICAL IMAGE RULE: NEVER USE LOCAL FILE NAMES 
 FORBIDDEN: url('iphone-15.jpg'), url('macbook-pro.jpg'), url('apple-watch.jpg')
 REQUIRED: Use full HTTPS URLs: url('https://images.unsplash.com/photo-xxx')

CRITICAL RULES:
1. Generate EVERY single item provided in the data - NO EXCEPTIONS
2. Never use "..." or truncation phrases
3. Never add explanatory notes about implementation
4. Count items as you generate them: 1, 2, 3... up to the final number
5. Use real URLs and data from the scraped content
6. For images, ONLY use complete HTTPS URLs - NO local files

 FOR APPLE PRODUCTS, USE THESE EXACT BACKGROUND IMAGES:
- iPhone 15 Pro: url('https://images.unsplash.com/photo-1592899677977-9c10ca588bbd?w=1200&h=800&fit=crop&auto=format')
- iPhone 15: url('https://images.unsplash.com/photo-1603791239113-3818cd1ef987?w=1200&h=800&fit=crop&auto=format')
- Apple Watch: url('https://images.unsplash.com/photo-1606220945770-b5b6c2c55bf1?w=1200&h=800&fit=crop&auto=format')
- MacBook Pro: url('https://images.unsplash.com/photo-1541807084-5c52b6b3adef?w=1200&h=800&fit=crop&auto=format')
- iPad: url('https://images.unsplash.com/photo-1585790050230-5dd28404ccb9?w=1200&h=800&fit=crop&auto=format')

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
        """Build a simple, focused prompt for generic website cloning"""
        data = scraped_data
        url = data.get('url', '')
        
        # Build navigation enforcement first
        nav_enforcement = []
        navigation = data.get('navigation', {})
        if navigation.get('headerLinks'):
            nav_enforcement.extend([
                " MANDATORY NAVIGATION IMPLEMENTATION (NO ALTERNATIVES ALLOWED):",
                "",
                "COPY THIS EXACT CSS (NO MODIFICATIONS):",
                "nav { background: rgba(0,0,0,0.8); height: 44px; position: fixed; top: 0; width: 100%; z-index: 9999; backdrop-filter: saturate(180%) blur(20px); }",
                ".nav-container { max-width: 980px; margin: 0 auto; display: flex; align-items: center; height: 100%; padding: 0 22px; position: relative; }",
                ".nav-logo { position: absolute; left: 22px; top: 50%; transform: translateY(-50%); z-index: 10; }",
                ".nav-logo svg { width: 14px; height: 44px; fill: #f5f5f7; display: block; }",
                ".nav-center { width: 100%; display: flex; justify-content: center; align-items: center; gap: 35px; margin: 0 60px; }",
                ".nav-center a { color: #f5f5f7; text-decoration: none; font-size: 12px; font-weight: 400; letter-spacing: -0.01em; padding: 0 8px; transition: opacity 0.3s; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif; }",
                ".nav-center a:hover { opacity: 0.8; }",
                "body { padding-top: 44px; margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif; }",
                "",
                "COPY THIS EXACT HTML (NO MODIFICATIONS):",
                "<nav>",
                "  <div class='nav-container'>",
                "    <div class='nav-logo'>",
                "      <svg width='16' height='44' viewBox='0 0 16 44' fill='#f5f5f7'><path d='M8.074 31.612c-1.155 0-1.976-.711-3.646-.711-1.776 0-2.3.679-3.544.711-2.489.086-4.688-2.789-6.306-5.611-3.223-5.611 0.844-14.1 5.559-13.8 2.144.134 3.344 1.289 5.026 1.289 1.681 0 2.67-1.289 5.113-1.289 1.833 0 3.404.956 4.606 2.589-4.034 2.211-3.378 7.977.889 9.944-.755 1.944-1.722 3.889-3.111 5.6-1.256 1.544-2.644 2.278-4.586 2.278zm-1.355-19.956c-.089-2.266 1.689-4.111 3.778-4.244 0.267 2.4-1.6 4.244-3.778 4.244z'/></svg>",
                "    </div>",
                "    <div class='nav-center'>",
                "      <a href='#'>Store</a>",
                "      <a href='#'>Mac</a>",
                "      <a href='#'>iPad</a>",
                "      <a href='#'>iPhone</a>",
                "      <a href='#'>Watch</a>",
                "      <a href='#'>Vision</a>",
                "      <a href='#'>AirPods</a>",
                "      <a href='#'>TV & Home</a>",
                "      <a href='#'>Entertainment</a>",
                "      <a href='#'>Accessories</a>",
                "      <a href='#'>Support</a>",
                "    </div>",
                "  </div>",
                "</nav>",
                "",
                "ALSO ADD THESE SECTION STYLES:",
                ".product-section { border-bottom: 1px solid #d2d2d7; margin-bottom: 11px; padding-bottom: 40px; }",
                ".section-divider { border-bottom: 1px solid #d2d2d7; margin: 20px 0; }",
                ".product-card { transition: transform 0.3s ease; border-radius: 18px; overflow: hidden; }",
                ".product-card:hover { transform: scale(1.02); }",
                "",
            ])
        
        # Add navigation enforcement at the top
        prompt_parts = [
            f"Clone this website into a complete HTML page: {url}",
            "",
            "CRITICAL IMPLEMENTATION RULES:",
            "1. Create a COMPLETE, FULLY FUNCTIONAL HTML page",
            "2. Include ALL content sections found in the scraped data",
            "3. Use modern CSS with responsive design",
            "4. Maintain the original visual hierarchy and layout",
            "5. Ensure all text is readable with proper contrast",
            "",
        ]
        
        # Add navigation enforcement at the top
        prompt_parts.extend(nav_enforcement)
        
        # Define articles from data
        articles = data.get('articles', [])
        
        # Add comprehensive image information
        hero_images = data.get('hero_images', [])
        product_images = data.get('product_images', [])
        logo_images = data.get('logo_images', [])
        
        if hero_images or product_images:
            prompt_parts.append(f"🎨 IMAGE SYSTEM ({len(hero_images)} heroes, {len(product_images)} products):")
            prompt_parts.extend([
                "",
                " CRITICAL IMAGE & CARD IMPLEMENTATION RULES:",
                "- NEVER use logo images as product backgrounds",
                "- Always prioritize hero images for main sections", 
                "- Include ALL background images that were extracted from original site",
                "- Add proper image dimensions and loading attributes with fallbacks",
                "- Use high-quality placeholder images if original images fail to load",
                "- Ensure all product sections have their corresponding background images",
                "- Match original image placement and styling exactly",
                "- Add proper aspect ratios and object-fit for consistent image display",
                "",
                " ENHANCED CSS FOR SECTIONS AND CARDS (COPY EXACTLY):",
                "/* CLEAN APPLE-STYLE CSS */",
                "body { margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #fff; }",
                ".product-section { padding: 80px 20px; text-align: center; border-bottom: 1px solid #d2d2d7; }",
                ".product-card { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }",
                ".product-content { margin-bottom: 40px; }",
                ".product-title { font-size: 48px; font-weight: 600; color: #1d1d1f; margin: 0 0 10px; line-height: 1.1; }",
                ".product-subtitle { font-size: 24px; color: #86868b; margin: 0 0 30px; font-weight: 400; }",
                ".product-links { display: flex; gap: 30px; justify-content: center; margin-bottom: 40px; }",
                ".product-links a { color: #0071e3; text-decoration: none; font-size: 21px; font-weight: 400; }",
                ".product-links a:hover { text-decoration: underline; }",
                ".product-image-container { width: 100%; max-width: 800px; margin: 0 auto; position: relative; }",
                ".product-image { width: 100%; height: auto; max-height: 500px; object-fit: contain; display: block; border-radius: 0; }",
                ".hero-section { padding: 80px 20px; text-align: center; background: linear-gradient(135deg, #000 0%, #1a1a1a 100%); color: white; }",
                ".hero-title { font-size: 56px; font-weight: 600; margin: 0 0 10px; line-height: 1.1; color: white !important; }",
                ".hero-subtitle { font-size: 28px; margin: 0 0 30px; color: #a1a1a6; font-weight: 400; }",
                ".hero-image { width: 100%; max-width: 800px; height: auto; max-height: 600px; object-fit: contain; margin: 40px auto; display: block; }",
                "",
                "/* Apple Watch Section Specific Styles */",
                ".watch-section { background: linear-gradient(135deg, #000 0%, #1a1a1a 100%); color: white !important; padding: 80px 20px; text-align: center; }",
                ".watch-title { font-size: 72px; font-weight: 700; color: white !important; margin: 0 0 10px; line-height: 1.1; letter-spacing: -2px; }",
                ".watch-series { font-size: 32px; color: #a1a1a6 !important; margin: 0 0 20px; font-weight: 400; }",
                ".watch-subtitle { font-size: 28px; color: white !important; margin: 0 0 30px; font-weight: 400; }",
                "h1, h2, h3 { color: inherit; }",
                ".product-section.dark { background: #000; color: white; }",
                ".product-section.dark .product-title { color: white !important; }",
                ".product-section.dark .product-subtitle { color: #a1a1a6 !important; }",
                "",
                "/* Responsive Design */",
                "@media (max-width: 768px) {",
                "  .product-title { font-size: 32px; }",
                "  .product-subtitle { font-size: 19px; }",
                "  .hero-title { font-size: 36px; }",
                "  .hero-subtitle { font-size: 21px; }",
                "  .product-links { flex-direction: column; gap: 15px; }",
                "}",
                "",
                " SIMPLE IMAGE SYSTEM (WORKING SOLUTION):",
                "",
                "/* Image CSS Rules */",
                "img { max-width: 100%; height: auto; display: block; margin: 0 auto; }",
                ".product-image { width: 100%; max-width: 600px; height: auto; object-fit: contain; }",
                ".hero-image { width: 100%; max-width: 800px; height: auto; object-fit: contain; }",
                "",
                " RESPONSIVE GRID LAYOUT (ADD TO CSS):",
                ".products-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 40px; max-width: 1200px; margin: 0 auto; padding: 0 20px; }",
                ".product-row { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 40px; margin: 60px 0; }",
                ".product-content { flex: 1; min-width: 300px; }",
                ".product-visual { flex: 1; min-width: 300px; text-align: center; }",
                "",
                " REQUIRED HTML STRUCTURE FOR EACH PRODUCT:",
                "<section class='product-section'>",
                "  <div class='product-card'>",
                "    <h2 class='product-title'>Product Name</h2>",
                "    <p class='product-subtitle'>Product Description</p>",
                "    <div class='product-links'>",
                "      <a href='#'>Learn more ></a>",
                "      <a href='#'>Buy ></a>",
                "    </div>",
                "    <img class='product-image' src='image-url' alt='Product Name' loading='lazy' onerror=\"this.src='fallback-url'; this.onerror=null;\">",
                "  </div>",
                "</section>",
                "",
                " APPLE-STYLE COLOR SCHEME:",
                "Primary Text: #1d1d1f | Secondary Text: #86868b | Links: #0071e3 | Background: #f5f5f7 | Dark Background: #000",
                "",
            ])
            
            if hero_images:
                prompt_parts.append("✨ HERO IMAGES (USE FOR MAIN SECTIONS):")
                for img in hero_images[:8]:  # Top 8 hero images
                    src = img.get('src', '')
                    alt = img.get('alt', '')
                    quality_score = img.get('quality_score', 0)
                    if src:
                        prompt_parts.append(f"   {src} (quality: {quality_score}) - {alt}")
                prompt_parts.extend([
                    "  → Use these for hero sections with .hero-image class",
                    "  → Apply proper aspect ratios and object-fit: contain",
                    ""
                ])
            
            if product_images:
                prompt_parts.append(" PRODUCT IMAGES (PRIORITIZE THESE FOR SPECIFIC PRODUCTS):")
                
                # Categorize images by product type for better matching
                iphone_images = []
                macbook_air_images = []
                macbook_pro_images = []
                ipad_images = []
                watch_images = []
                other_images = []
                
                for img in product_images[:15]:  # Check more images for better categorization
                    src = img.get('src', '').lower()
                    alt = img.get('alt', '').lower()
                    quality_score = img.get('quality_score', 0)
                    
                    if any(keyword in src + alt for keyword in ['iphone', 'phone', 'mobile']):
                        iphone_images.append(img)
                    elif any(keyword in src + alt for keyword in ['macbook air', 'air']):
                        macbook_air_images.append(img)
                    elif any(keyword in src + alt for keyword in ['macbook pro', 'pro', 'laptop', 'mac']):
                        macbook_pro_images.append(img)
                    elif any(keyword in src + alt for keyword in ['watch', 'series']):
                        watch_images.append(img)
                    elif any(keyword in src + alt for keyword in ['ipad', 'tablet']):
                        ipad_images.append(img)
                    else:
                        other_images.append(img)
                
                if iphone_images:
                    prompt_parts.append("   iPhone 15 Pro Images (BEST MATCHES):")
                    for img in iphone_images[:3]:
                        src = img.get('src', '')
                        alt = img.get('alt', '')
                        quality_score = img.get('quality_score', 0)
                        if src:
                            prompt_parts.append(f"     {src} (quality: {quality_score}) - {alt}")
                
                if macbook_air_images:
                    prompt_parts.append("   MacBook Air 15\" Images (BEST MATCHES):")
                    for img in macbook_air_images[:3]:
                        src = img.get('src', '')
                        alt = img.get('alt', '')
                        quality_score = img.get('quality_score', 0)
                        if src:
                            prompt_parts.append(f"     {src} (quality: {quality_score}) - {alt}")
                
                if macbook_pro_images:
                    prompt_parts.append("  MacBook Pro Images (BEST MATCHES):")
                    for img in macbook_pro_images[:3]:
                        src = img.get('src', '')
                        alt = img.get('alt', '')
                        quality_score = img.get('quality_score', 0)
                        if src:
                            prompt_parts.append(f"     {src} (quality: {quality_score}) - {alt}")
                
                if watch_images:
                    prompt_parts.append("   Apple Watch Series 9 Images (BEST MATCHES):")
                    for img in watch_images[:3]:
                        src = img.get('src', '')
                        alt = img.get('alt', '')
                        quality_score = img.get('quality_score', 0)
                        if src:
                            prompt_parts.append(f"     {src} (quality: {quality_score}) - {alt}")
                
                if ipad_images:
                    prompt_parts.append("   iPad Images (BEST MATCHES):")
                    for img in ipad_images[:3]:
                        src = img.get('src', '')
                        alt = img.get('alt', '')
                        quality_score = img.get('quality_score', 0)
                        if src:
                            prompt_parts.append(f"     {src} (quality: {quality_score}) - {alt}")
                
                prompt_parts.extend([
                    "",
                    "   PRIORITIZATION RULES:",
                    "  → Use categorized images above for matching products",
                    "  → iPhone images go with 'Titanium. So strong. So light. So Pro.'",
                    "  → MacBook Air images go with 'Impressively big. Impossibly thin.'",
                    "  → MacBook Pro images go with 'Mind-blowing. Head-turning.' - MUST SHOW IMAGE",
                    "  → Apple Watch images go with 'Smarter. Brighter. Mightier.'",
                    "  → iPad images go with 'Lovable. Drawable. Magical.'",
                    "  → For Watch section: USE DARK BACKGROUND with WHITE TEXT",
                    "",

                    "  → Add the onerror fallback to all img tags",
                    ""
                ])
            
            if logo_images:
                prompt_parts.append("LOGO IMAGES (USE ONLY FOR BRANDING, NOT BACKGROUNDS):")
                for img in logo_images[:3]:  # Top 3 logos
                    src = img.get('src', '')
                    alt = img.get('alt', '')
                    if src:
                        prompt_parts.append(f"  🏷️ {src} - {alt}")
            
            prompt_parts.append("")
        
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
                "",
                " EXACT HTML TEMPLATES FOR SPECIFIC PRODUCTS:",
                "",
                "<!-- iPhone 15 Pro Section -->",
                "<section class='product-section'>",
                "  <div class='product-card'>",
                "    <div class='product-content'>",
                "      <h2 class='product-title'>iPhone 15 Pro</h2>",
                "      <p class='product-subtitle'>Titanium. So strong. So light. So Pro.</p>",
                "      <div class='product-links'>",
                "        <a href='#'>Learn more ></a>",
                "        <a href='#'>Buy ></a>",
                "      </div>",
                "    </div>",
                "    <div class='product-image-container'>",
                "      <img src='https://images.unsplash.com/photo-1592899677977-9c10ca588bbd?w=800&h=600&fit=crop&auto=format' alt='iPhone 15 Pro' class='product-image' loading='lazy' onerror=\"this.src='https://images.unsplash.com/photo-1611261954895-3040905d4432?w=800&h=600&fit=crop'; this.onerror=null;\" />",
                "    </div>",
                "  </div>",
                "</section>",
                "",
                "<!-- MacBook Air 15\" Section -->",
                "<section class='product-section'>",
                "  <div class='product-card'>",
                "    <div class='product-content'>",
                "      <h2 class='product-title'>MacBook Air 15\"</h2>",
                "      <p class='product-subtitle'>Impressively big. Impossibly thin.</p>",
                "      <div class='product-links'>",
                "        <a href='#'>Learn more ></a>",
                "        <a href='#'>Buy ></a>",
                "      </div>",
                "    </div>",
                "    <div class='product-image-container'>",
                "      <img src='https://images.unsplash.com/photo-1541807084-5c52b6b3adef?w=800&h=600&fit=crop&auto=format' alt='MacBook Air 15 inch' class='product-image' loading='lazy' onerror=\"this.src='https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=800&h=600&fit=crop'; this.onerror=null;\" />",
                "    </div>",
                "  </div>",
                "</section>",
                "",
                "<!-- MacBook Pro Section -->",
                "<section class='product-section'>",
                "  <div class='product-card'>",
                "    <div class='product-content'>",
                "      <h2 class='product-title'>MacBook Pro</h2>",
                "      <p class='product-subtitle'>Mind-blowing. Head-turning.</p>",
                "      <div class='product-links'>",
                "        <a href='#'>Learn more ></a>",
                "        <a href='#'>Buy ></a>",
                "      </div>",
                "    </div>",
                "    <div class='product-image-container'>",
                "      <img src='image-url' alt='MacBook Pro' class='product-image' loading='lazy' />",
                "    </div>",
                "  </div>",
                "</section>",
                "",
                "<!-- Apple Watch Section (DARK BACKGROUND) -->",
                "<section class='product-section watch-section dark'>",
                "  <div class='product-card'>",
                "    <div class='product-content'>",
                "      <h1 class='watch-title'>WATCH</h1>",
                "      <p class='watch-series'>SERIES 9</p>",
                "      <p class='watch-subtitle'>Smarter. Brighter. Mightier.</p>",
                "      <div class='product-links'>",
                "        <a href='#' style='color: #0071e3;'>Learn more ></a>",
                "        <a href='#' style='color: #0071e3;'>Buy ></a>",
                "      </div>",
                "    </div>",
                "    <div class='product-image-container'>",
                "      <img src='https://images.unsplash.com/photo-1606220945770-b5b6c2c55bf1?w=800&h=600&fit=crop&auto=format' alt='Apple Watch Series 9' class='product-image' loading='lazy' onerror=\"this.src='https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=800&h=600&fit=crop'; this.onerror=null;\" />",
                "    </div>",
                "  </div>",
                "</section>",
                "",
                "<!-- iPad Section -->",
                "<section class='product-section'>",
                "  <div class='product-card'>",
                "    <div class='product-content'>",
                "      <h2 class='product-title'>iPad</h2>",
                "      <p class='product-subtitle'>Lovable. Drawable. Magical.</p>",
                "      <div class='product-links'>",
                "        <a href='#'>Learn more ></a>",
                "        <a href='#'>Buy ></a>",
                "      </div>",
                "    </div>",
                "    <div class='product-image-container'>",
                "      <img src='https://images.unsplash.com/photo-1585790050230-5dd28404ccb9?w=800&h=600&fit=crop&auto=format' alt='iPad' class='product-image' loading='lazy' onerror=\"this.src='https://images.unsplash.com/photo-1561154464-82e9adf32764?w=800&h=600&fit=crop'; this.onerror=null;\" />",
                "    </div>",
                "  </div>",
                "</section>",
                "",
                " CRITICAL IMAGE REQUIREMENTS:",
                "   ALWAYS wrap images in .product-image-container",
                "   ALWAYS add .product-image class to img tags", 
                "   ALWAYS include proper alt text",
                "   ALWAYS add loading='lazy' attribute",
                "   NEVER use fixed heights - let images scale naturally",
                "   ALWAYS use object-fit: contain for product images",
                "",
                " CRITICAL: NEVER USE LOCAL FILES LIKE 'iphone-15.jpg' ",
                " FORBIDDEN: url('iphone-15.jpg')  FORBIDDEN: url('apple-watch.jpg')",
                " REQUIRED: Use ONLY these complete HTTPS URLs ",
                "",
                " MANDATORY CSS RULES - COPY EXACTLY:",
                ".iphone-15-pro { background-image: url('https://images.unsplash.com/photo-1592899677977-9c10ca588bbd?w=1200&h=800&fit=crop&auto=format'); background-size: cover; background-position: center; color: #f5f5f7; text-shadow: 1px 1px 2px rgba(0,0,0,0.8); }",
                ".apple-watch { background-image: url('https://images.unsplash.com/photo-1606220945770-b5b6c2c55bf1?w=1200&h=800&fit=crop&auto=format'); background-size: cover; background-position: center; color: #f5f5f7; text-shadow: 1px 1px 2px rgba(0,0,0,0.8); }",
                ".macbook-pro { background-image: url('https://images.unsplash.com/photo-1541807084-5c52b6b3adef?w=1200&h=800&fit=crop&auto=format'); background-size: cover; background-position: center; color: #1d1d1f; }",
                ".ipad-section { background-image: url('https://images.unsplash.com/photo-1585790050230-5dd28404ccb9?w=1200&h=800&fit=crop&auto=format'); background-size: cover; background-position: center; color: #1d1d1f; }",
                ".iphone-15 { background-image: url('https://images.unsplash.com/photo-1603791239113-3818cd1ef987?w=1200&h=800&fit=crop&auto=format'); background-size: cover; background-position: center; color: #f5f5f7; text-shadow: 1px 1px 2px rgba(0,0,0,0.8); }",
                "",
                " EXAMPLE IMPLEMENTATION:",
                "<section class=\"hero iphone-15-pro\">",
                "  <h1>iPhone 15 Pro</h1>",
                "  <p>Titanium. So strong. So light. So Pro.</p>",
                "</section>",
                "",
                "<section class=\"product-tile apple-watch\">",
                "  <h2>WATCH SERIES 9</h2>",
                "  <p>Smarter. Brighter. Mightier.</p>",
                "</section>"
                ""
            ])
        
        # Add divider information
        dividers = data.get('dividers', [])
        if dividers:
            prompt_parts.extend([
                f"📏 SECTION DIVIDERS ({len(dividers)} found):",
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
            requirements.append("- CRITICAL: Use Apple's signature navigation design patterns")
            requirements.append("- Navigation background: Dark (#1d1d1f or #000000) with slight transparency")
            requirements.append("- Navigation text color: Light gray/white (#f5f5f7, #d2d2d7)")
            requirements.append("- Navigation height: 44px (Apple standard) with proper padding")
            requirements.append("- Font: Use Apple system fonts (-apple-system, BlinkMacSystemFont, 'SF Pro Display')")
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
        svg_logos = data.get('svgLogos', [])
        
        if images or background_images or logo_images or svg_logos:
            requirements.append("IMAGES AND MEDIA:")
            
            # Enhanced Apple SVG logo detection and handling
            if svg_logos:
                requirements.append(f"- APPLE SVG LOGO IMPLEMENTATION ({len(svg_logos)} found):")
                
                apple_svg_logos = [svg for svg in svg_logos if svg.get('isAppleLogo', False) or svg.get('isInNavigation', False)]
                if apple_svg_logos:
                    for svg in apple_svg_logos[:1]:  # Use the first Apple SVG logo found
                        view_box = svg.get('viewBox', '0 0 14 44')
                        paths = svg.get('paths', [])
                        fill_color = svg.get('fill', '#f5f5f7')
                        width = svg.get('width', '14')
                        height = svg.get('height', '44')
                        
                        requirements.append(f"  • SVG ViewBox: {view_box}")
                        requirements.append(f"  • SVG Dimensions: {width}x{height}")
                        requirements.append(f"  • Fill Color: {fill_color}")
                        requirements.append(f"  • Path Count: {len(paths)}")
                        if paths:
                            for i, path in enumerate(paths[:2], 1):  # Show first 2 paths
                                path_data = path.get('d', '')[:100] + '...' if len(path.get('d', '')) > 100 else path.get('d', '')
                                requirements.append(f"    Path {i}: {path_data}")
            
            requirements.extend([
                "",
                "CRITICAL APPLE SVG LOGO IMPLEMENTATION:",
                "- Use COMPLETE Apple SVG logo with ALL path data - no truncation",
                "- Set SVG dimensions: width='20' height='20' (scaled down from 14x44)",
                "- ViewBox MUST be '0 0 14 44' to ensure full logo visibility", 
                "- Fill color: #f5f5f7 (Apple's nav text color)",
                "- Position SVG logo on the FAR LEFT of navigation with proper spacing",
                "- Wrap SVG in clickable link: <a href='/' class='nav-logo'>...svg...</a>",
                "- Add hover effect: opacity: 0.8 on hover transition",
                "- Ensure the SVG renders as the full Apple logo, not partial or cut off",
                "- Test that all path data is complete and not missing parts",
                "",
                "ENHANCED NAVIGATION LAYOUT REQUIREMENTS:",
                "- Navigation container: width: 100%, max-width: 980px, margin: 0 auto",
                "- Navigation inner content: display: flex, align-items: center, justify-content: space-between",
                "- Logo container: flex-shrink: 0, margin-right: auto, padding: 0 22px 0 0",
                "- Navigation links: display: flex, align-items: center, gap: 0",
                "- Each nav link: padding: 0 10px, height: 44px, display: flex, align-items: center",
                "- Use CSS Grid or Flexbox for perfect alignment across all screen sizes",
                "- Ensure navigation bar has proper backdrop-filter and transparency",
                "- Logo must be fully visible and not clipped at any viewport size",
                ""
            ])
            
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
                    "- Ensure logo loads correctly and is not broken or showing as text",
                    "",
                    "NAVIGATION STRUCTURE TEMPLATE:",
                    "<nav style='background: rgba(0,0,0,0.8); height: 44px; position: fixed; top: 0; width: 100%; z-index: 9999; backdrop-filter: saturate(180%) blur(20px);'>",
                    "  <div style='max-width: 980px; margin: 0 auto; display: flex; align-items: center; height: 100%; padding: 0 22px;'>",
                    "    <a href='/' style='flex-shrink: 0; margin-right: auto; display: flex; align-items: center;'>",
                    "      <!-- APPLE SVG LOGO HERE with proper dimensions and paths -->",
                    "    </a>",
                    "    <div style='display: flex; align-items: center; gap: 0;'>",
                    "      <!-- Navigation links here with proper spacing -->",
                    "    </div>",
                    "  </div>",
                    "</nav>",
                    ""
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
                
                # Separate high-quality images from logos and low-quality images
                hero_images = [bg for bg in background_images if bg.get('imageType') == 'hero' and bg.get('isHighQuality', False)]
                product_images = [bg for bg in background_images if bg.get('imageType') == 'product' and bg.get('isHighQuality', False)]
                logo_images = [bg for bg in background_images if bg.get('imageType') == 'logo' or bg.get('isLogo', False)]
                
                # Sort by quality score (highest first)
                all_quality_images = sorted(
                    [bg for bg in background_images if bg.get('isHighQuality', False) and not bg.get('isLogo', False)],
                    key=lambda x: x.get('qualityScore', 0),
                    reverse=True
                )
                
                if hero_images:
                    requirements.append(f"  HERO IMAGES ({len(hero_images)} found) - USE THESE FOR MAIN SECTIONS:")
                    for hero in hero_images[:3]:  # Show top 3 hero images
                        element = hero.get('element', 'div')
                        bg_img = hero.get('backgroundImage', '')
                        score = hero.get('qualityScore', 0)
                        requirements.append(f"    • {element} (score: {score}): {bg_img}")
                    requirements.append("")
                
                if product_images:
                    requirements.append(f"  PRODUCT IMAGES ({len(product_images)} found) - USE FOR PRODUCT TILES:")
                    for prod in product_images[:3]:  # Show top 3 product images
                        element = prod.get('element', 'div')
                        bg_img = prod.get('backgroundImage', '')
                        score = prod.get('qualityScore', 0)
                        requirements.append(f"    • {element} (score: {score}): {bg_img}")
                    requirements.append("")
                
                if logo_images:
                    requirements.append(f"  ⚠️ LOGO IMAGES DETECTED ({len(logo_images)} found) - DO NOT USE AS BACKGROUNDS:")
                    for logo in logo_images[:2]:  # Show first 2 logos as examples
                        bg_img = logo.get('backgroundImage', '')
                        requirements.append(f"    • AVOID: {bg_img}")
                    requirements.append("")
                
                requirements.extend([
                    "  CRITICAL IMAGE USAGE RULES:",
                    "  - NEVER use logo images (containing 'logo', 'nav', 'globalnav') as backgrounds for product tiles",
                    "  - PRIORITIZE hero images (/heroes/, hero_) for main sections", 
                    "  - USE product images for product tiles, ensuring they're not logos",
                    "  - PREFER .jpg/.jpeg files for photo backgrounds over .png logos",
                    "  - If an image has qualityScore < 30, find a better alternative",
                    "  - Hero sections should use images from /heroes/ folder when available",
                    "  - Product tiles should use actual product photos, not logo graphics",
                    ""
                ])
            
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
                "APPLE FONT IMPLEMENTATION REQUIREMENTS:",
                "- PRIMARY: Use Apple's official font stack:",
                "  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Icons', 'Helvetica Neue', Helvetica, Arial, sans-serif;",
                "- Navigation text: 14px, font-weight: 400, letter-spacing: -0.016em",
                "- Hero text: Large sizes with proper letter-spacing (-0.022em for 17px+)",
                "- Body text: 17px, font-weight: 400, line-height: 1.47",
                "",
                "APPLE TYPOGRAPHY COLOR SYSTEM:",
                "- Navigation text: #F5F5F7 (light gray on dark nav)",
                "- Primary text: #1D1D1F (Apple's signature dark gray)",
                "- Secondary text: #86868B (Apple's medium gray)",
                "- Hero/large text: #1D1D1F with proper contrast",
                "- Link colors: #007AFF (Apple blue) for interactive elements",
                "",
                "CRITICAL TYPOGRAPHY RULES:",
                "- Apply Apple's exact letter-spacing values consistently",
                "- Use proper line-height ratios (1.47 for body, 1.2 for headlines)",
                "- Ensure text renders crisply with -webkit-font-smoothing: antialiased",
                "- Match original font weights and sizes exactly from detected typography"
            ])
            requirements.append("")
        
        # Interactive buttons and CTAs
        buttons = data.get('buttons', [])
        cta_elements = data.get('ctaElements', [])
        
        if buttons or cta_elements:
            requirements.append("INTERACTIVE ELEMENTS AND BUTTONS:")
            
            if buttons:
                requirements.append(f"- BUTTONS ({len(buttons)} found):")
                for btn in buttons[:8]:  # Show first 8 buttons
                    text = btn.get('text', '').strip()
                    tag = btn.get('tagName', 'button')
                    href = btn.get('href', '')
                    bg_color = btn.get('style', {}).get('backgroundColor', '')
                    if text:
                        button_info = f"  • {text} ({tag})"
                        if href:
                            button_info += f" → {href}"
                        if bg_color and bg_color != 'rgba(0, 0, 0, 0)':
                            button_info += f" [{bg_color}]"
                        requirements.append(button_info)
            
            if cta_elements:
                requirements.append(f"- CALL-TO-ACTION LINKS ({len(cta_elements)} found):")
                for cta in cta_elements[:6]:  # Show first 6 CTAs
                    text = cta.get('text', '').strip()
                    href = cta.get('href', '')
                    if text and href:
                        requirements.append(f"  • \"{text}\" → {href}")
            
            requirements.extend([
                "",
                "APPLE-STYLE BUTTON DESIGN REQUIREMENTS:",
                "- Primary button (Learn more): Blue (#007AFF) with white text",
                "- Button dimensions: padding: 12px 22px, border-radius: 8px",
                "- Typography: font-weight: 400, font-size: 17px, letter-spacing: -0.022em",
                "- Button font: Use Apple system fonts (-apple-system, BlinkMacSystemFont)",
                "- Hover effect: Slightly darker blue (#0051D5) with smooth transition",
                "- Shadow: subtle drop shadow (0 2px 4px rgba(0,0,0,0.1))",
                "- Active state: transform: scale(0.96) for brief press feedback",
                "- Focus state: outline: 2px solid #007AFF with 2px offset",
                "- Transition: all properties with 0.2s ease timing",
                "",
                "SECONDARY BUTTON STYLING (if present):",
                "- Secondary buttons: Light background (#F2F2F7) with dark text (#1D1D1F)",
                "- Same dimensions and transitions as primary buttons",
                "- Hover: Slightly darker background (#E5E5EA)",
                "",
                "CTA INTERACTION REQUIREMENTS:",
                "- Make ALL buttons and CTAs fully clickable and interactive",
                "- Ensure buttons have proper cursor: pointer",
                "- Include smooth micro-interactions on hover and click",
                "- Maintain Apple's accessibility standards",
                "- Include 'Learn more' and 'Buy' buttons exactly as in original design",
                "- Ensure button text is center-aligned and properly sized"
            ])
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
                    "- Add interactive buttons (Learn more, Buy, etc.) within each card",
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
        
        # Enhanced Apple color scheme detection
        colors = data.get('colors', {})
        if colors:
            requirements.append("APPLE COLOR SYSTEM IMPLEMENTATION:")
            
            # Extract navigation colors
            nav_colors = colors.get('navigationColors', {})
            if nav_colors:
                nav_bg = nav_colors.get('backgroundColor', '')
                nav_text = nav_colors.get('textColor', '')
                if nav_bg:
                    requirements.append(f"- Detected navigation background: {nav_bg}")
                if nav_text:
                    requirements.append(f"- Detected navigation text color: {nav_text}")
            
            # Apple-specific color detection
            apple_colors = colors.get('hasAppleColors', {})
            if apple_colors:
                if apple_colors.get('darkNavigation'):
                    requirements.append("- Dark navigation detected - use Apple's navigation styling")
                if apple_colors.get('lightText'):
                    requirements.append("- Light text on navigation detected - maintain Apple's contrast")
                if apple_colors.get('appleBlue'):
                    requirements.append("- Apple blue detected - ensure proper implementation")
            
            # Color implementation requirements
            requirements.extend([
                "",
                "MANDATORY APPLE COLOR IMPLEMENTATION:",
                "- Navigation background: rgba(29, 29, 31, 0.8) or #1d1d1f with 0.8 opacity",
                "- Navigation text: #f5f5f7 (Apple's standard navigation text color)",
                "- Navigation hover: rgba(245, 245, 247, 0.8) for subtle hover effects",
                "",
                "CRITICAL BODY TEXT COLOR REQUIREMENTS:",
                "- ALL body text, headings, paragraphs: color: #1d1d1f (Apple's dark text)",
                "- Secondary descriptive text: color: #86868b (Apple's secondary gray)", 
                "- Product tile text: color: #1d1d1f (NEVER white on light backgrounds)",
                "- Hero section text: color: #1d1d1f on light backgrounds, #ffffff on dark images",
                "- Button text: #1d1d1f on light buttons, #ffffff on dark/blue buttons",
                "",
                "LINK AND INTERACTIVE COLORS:",
                "- Interactive links: color: #007aff (Apple's system blue)",
                "- CTA buttons: background: #007aff, color: #ffffff",
                "- 'Learn more' links: color: #007aff with hover effects",
                "",
                "BACKGROUND COLORS:",
                "- Page background: #ffffff or #fbfbfd",
                "- Product tiles: light backgrounds (#ffffff, #f5f5f7)",
                "- Navigation: rgba(29, 29, 31, 0.8) with backdrop blur",
                "",
                "COLOR CONTRAST RULES (CRITICAL):",
                "- NEVER use white text (#ffffff) on light backgrounds",
                "- ALWAYS use dark text (#1d1d1f) for body content on light backgrounds",
                "- Light text (#f5f5f7) ONLY for navigation on dark navigation bar",
                "- Ensure all text meets WCAG AA contrast requirements",
                "- Product cards must have dark text for readability",
                ""
            ])
            
            # Include detected colors for reference
            text_colors = colors.get('textColors', [])
            if text_colors:
                requirements.append(f"- Reference detected colors: {', '.join(text_colors[:8])}")
            
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
        
        # Add navigation structure information
        navigation = data.get('navigation', {})
        header_structure = navigation.get('headerStructure', {})
        header_links = navigation.get('headerLinks', [])
        
        if header_structure or header_links:
            requirements.append(f"APPLE NAVIGATION SYSTEM ({len(header_links)} links):")
            
            requirements.extend([
                "",
                "🔥 MANDATORY APPLE NAVIGATION IMPLEMENTATION - FOLLOW EXACTLY:",
                "",
                "NAVIGATION CSS (COPY EXACTLY):",
                "nav { background: rgba(0,0,0,0.8); height: 44px; position: fixed; top: 0; width: 100%; z-index: 9999; backdrop-filter: saturate(180%) blur(20px); }",
                ".nav-container { max-width: 980px; margin: 0 auto; display: flex; align-items: center; height: 100%; padding: 0 22px; position: relative; }",
                ".nav-logo { position: absolute; left: 22px; top: 50%; transform: translateY(-50%); }",
                ".nav-logo svg { width: 16px; height: 44px; fill: #f5f5f7; }",
                ".nav-center { flex: 1; display: flex; justify-content: center; align-items: center; gap: 35px; margin: 0 40px; }",
                ".nav-center a { color: #f5f5f7; text-decoration: none; font-size: 12px; font-weight: 400; letter-spacing: -0.01em; padding: 0 8px; transition: opacity 0.3s; }",
                ".nav-center a:hover { opacity: 0.8; }",
                "",
                "NAVIGATION HTML STRUCTURE (IMPLEMENT EXACTLY):",
                "<nav>",
                "  <div class='nav-container'>",
                "    <div class='nav-logo'>",
                "      <svg width='16' height='44' viewBox='0 0 16 44' fill='#f5f5f7'><path d='M8.074 31.612c-1.155 0-1.976-.711-3.646-.711-1.776 0-2.3.679-3.544.711-2.489.086-4.688-2.789-6.306-5.611-3.223-5.611 0.844-14.1 5.559-13.8 2.144.134 3.344 1.289 5.026 1.289 1.681 0 2.67-1.289 5.113-1.289 1.833 0 3.404.956 4.606 2.589-4.034 2.211-3.378 7.977.889 9.944-.755 1.944-1.722 3.889-3.111 5.6-1.256 1.544-2.644 2.278-4.586 2.278zm-1.355-19.956c-.089-2.266 1.689-4.111 3.778-4.244 0.267 2.4-1.6 4.244-3.778 4.244z'/></svg>",
                "    </div>",
                "    <div class='nav-center'>",
                "      <a href='#'>Store</a>",
                "      <a href='#'>Mac</a>",
                "      <a href='#'>iPad</a>",
                "      <a href='#'>iPhone</a>",
                "      <a href='#'>Watch</a>",
                "      <a href='#'>Vision</a>",
                "      <a href='#'>AirPods</a>",
                "      <a href='#'>TV & Home</a>",
                "      <a href='#'>Entertainment</a>",
                "      <a href='#'>Accessories</a>",
                "      <a href='#'>Support</a>",
                "    </div>",
                "  </div>",
                "</nav>",
                "",
                "CARD/SECTION STYLING REQUIREMENTS:",
                "- Add subtle borders between product sections: border-bottom: 1px solid #d2d2d7",
                "- Use proper spacing: margin-bottom: 11px between sections",
                "- Ensure images are properly loaded with fallback handling",
                "- Add proper hover effects: transform: scale(1.02) on product cards",
                "",
                "IMAGE HANDLING REQUIREMENTS:",
                "- Always include width and height attributes for images",
                "- Use proper loading='lazy' for performance",
                "- Include alt text for all images",
                "- Add proper error handling: onerror=\"this.style.display='none'\"",
                "",
            ])
            
            if header_links:
                requirements.append("- Navigation Links:")
                for link in header_links[:12]:  # Show first 12 nav links
                    text = link.get('text', '').strip()
                    href = link.get('href', '#')
                    className = link.get('className', '')
                    if text and text not in ['', 'Apple']:
                        requirements.append(f"  • {text} → {href}")
        else:
            requirements.extend([
                "NAVIGATION STRUCTURE (Apple-style):",
                "- Create dark translucent navigation bar (background: rgba(0,0,0,0.8))",
                "- Position logo on far left, navigation links spread across remaining space",
                "- Use flexbox for perfect alignment and responsive behavior",
                "- Include Apple logo SVG with proper dimensions and white fill",
                "- Navigation height: 44px (Apple standard)",
                "- Add backdrop-filter: saturate(180%) blur(20px) for glass effect",
                ""
            ])
        
        return requirements

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
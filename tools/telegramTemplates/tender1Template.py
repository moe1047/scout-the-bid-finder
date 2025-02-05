def format_tender_message(tender) -> str:
    """
    Format a tender object into an HTML-formatted message for Telegram.
    
    Args:
        tender: Tender object containing tender details
        
    Returns:
        str: HTML-formatted message ready for Telegram
    """
    # Extract hashtags from title and organization
    words = set((tender.title + " " + tender.organization).split())
    hashtags = " ".join([f"#{word}" for word in words if len(word) > 3])[:50]  # Limit hashtags length
    
    html_message = f"""
<b>🔔 New Tender Alert!</b>

<b>Title:</b> {tender.title}

<i>📋 Key Details</i>
• <b>Organization:</b> {tender.organization}
• <b>Location:</b> {tender.location}
• <b>Posted Date:</b> {tender.posted_date}
• <b>Closing Date:</b> {tender.closing_date}

<i>📝 Description:</i>
{tender.tender_content}

<a href="{tender.url}">View Full Details</a>

<code>Source: {tender.source}</code>
<code>{hashtags}</code>
"""
    return html_message

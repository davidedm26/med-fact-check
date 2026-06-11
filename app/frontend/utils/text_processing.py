import re

def split_into_sentences(text):
    """Divide il testo in frasi usando la punteggiatura come separatore."""
    text = re.sub(r'\s+', ' ', text).strip()
    sentences = re.split(r'(?<=[.!?;])\s+', text)
    
    clean_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence.split()) >= 3 and len(sentence) >= 15:
            clean_sentences.append(sentence)
    
    if not clean_sentences:
        return [text]
    
    return clean_sentences

def highlight_quotes(text, supp, ref):
    """Evidenzia le citazioni supportate o confutate nel testo."""
    hl = text
    if isinstance(supp, str): supp = [supp]
    if isinstance(ref, str): ref = [ref]
    
    for q in (supp or []):
        if q and len(q) > 5:
            words = [re.escape(re.sub(r'\W', '', w)) for w in q.split() if re.sub(r'\W', '', w)]
            if words:
                pattern = re.compile(r'\W+'.join(words), re.IGNORECASE)
                hl = pattern.sub(r"<span class='eval-highlight-support'>\g<0></span>", hl)
                
    for q in (ref or []):
        if q and len(q) > 5:
            words = [re.escape(re.sub(r'\W', '', w)) for w in q.split() if re.sub(r'\W', '', w)]
            if words:
                pattern = re.compile(r'\W+'.join(words), re.IGNORECASE)
                hl = pattern.sub(r"<span class='eval-highlight-refute'>\g<0></span>", hl)
                
    return hl
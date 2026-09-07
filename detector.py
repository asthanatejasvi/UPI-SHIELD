import re
from transformers import pipeline

# ---------------------------------------------------------
# UPI-SHIELD : CONTEXTUAL SCAM DETECTOR
# ---------------------------------------------------------

# Zero-shot NLP model
classifier = pipeline(
    "zero-shot-classification",
    model="typeform/distilbert-base-uncased-mnli"
)

CATEGORIES = [
    "urgency or immediate action",
    "threat or coercion",
    "fake authority or impersonation",
    "payment manipulation",
    "request for OTP or UPI PIN",
    "fake refund scam",
    "KYC or account blocking scam"
]


# ---------------------------------------------------------
# Contextual keyword patterns
# ---------------------------------------------------------

PATTERNS = {
    "urgency or immediate action": [
        r"\b(immediately|urgent|urgently|right now|within \d+\s*(minutes?|hours?))\b",
        r"\b(act now|do it now|last warning|today only)\b"
    ],

    "threat or coercion": [
        r"\b(disconnect|disconnected|blocked|block|suspend|suspended|legal action)\b",
        r"\b(police|case|fine|penalty|arrest)\b"
    ],

    "fake authority or impersonation": [
        r"\b(bank officer|bank manager|police officer|electricity department)\b",
        r"\b(government official|customer care|cyber cell|official)\b",
        r"\b(i am calling from|calling from)\b"
    ],

    "payment manipulation": [
        r"\b(pay|payment|transfer|send money|deposit|upi|₹|\brs\.?\b)\b",
        r"\b(scan.*qr|qr.*scan|upi id)\b"
    ],

    "request for OTP or UPI PIN": [
        r"\b(otp|one time password|upi pin|pin|password|cvv)\b",
        r"\b(share|send|tell|provide).{0,20}\b(otp|pin|password)\b"
    ],

    "fake refund scam": [
        r"\b(refund|cashback|refund pending|refund verification)\b",
        r"\b(send.*(₹|rs|money)|pay.*(₹|rs|money)).{0,40}\b(refund)\b"
    ],

    "KYC or account blocking scam": [
        r"\b(kyc|re-kyc|account.*block|account.*suspend|verify.*account)\b",
        r"\b(update.*kyc|kyc.*expire|kyc.*expired)\b"
    ]
}


# ---------------------------------------------------------
# Rule-based contextual signal detection
# ---------------------------------------------------------

def detect_context_signals(text):
    text_lower = text.lower()

    signals = {}

    for category, patterns in PATTERNS.items():
        matched = []

        for pattern in patterns:
            if re.search(pattern, text_lower):
                matched.append(pattern)

        signals[category] = len(matched)

    return signals


# ---------------------------------------------------------
# UPI information extraction
# ---------------------------------------------------------

def extract_payment_info(text):

    # UPI ID
    upi_match = re.search(
        r'\b[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\b',
        text
    )

    # Amount
    amount_match = re.search(
        r'(?:₹|Rs\.?|INR)\s?[\d,]+(?:\.\d+)?',
        text,
        re.IGNORECASE
    )

    result = {
        "upi_id": upi_match.group(0) if upi_match else None,
        "amount": amount_match.group(0) if amount_match else None
    }

    return result


# ---------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------

def analyze_message(text):

    # NLP classification
    result = classifier(
        text,
        CATEGORIES,
        multi_label=True
    )

    nlp_scores = dict(
        zip(result["labels"], result["scores"])
    )

    # Contextual rules
    rule_signals = detect_context_signals(text)

    detected = []

    # Combine NLP + contextual signals
    for category in CATEGORIES:

        nlp_score = nlp_scores.get(category, 0)
        rule_score = rule_signals.get(category, 0)

        # Stronger score when both NLP and contextual rules agree
        combined_score = min(
            1.0,
            (nlp_score * 0.65) + (min(rule_score, 2) * 0.175)
        )

        if combined_score >= 0.42:
            detected.append({
                "category": category,
                "score": combined_score
            })

    # -----------------------------------------------------
    # Overall risk score
    # -----------------------------------------------------

    risk_score = 0

    for item in detected:
        risk_score += int(item["score"] * 25)

    # Extra contextual boost
    strong_signals = sum(
        1 for value in rule_signals.values()
        if value > 0
    )

    risk_score += strong_signals * 7

    risk_score = min(100, risk_score)

    # Risk level
    if risk_score >= 70:
        risk_level = "HIGH"
    elif risk_score >= 40:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    # -----------------------------------------------------
    # Explanation
    # -----------------------------------------------------

    explanations = []

    explanation_map = {
        "urgency or immediate action":
            "The message creates urgency and pressures the user to act quickly.",

        "threat or coercion":
            "The message uses threats such as disconnection, blocking, penalties or legal consequences.",

        "fake authority or impersonation":
            "The sender appears to use an authority or official identity to gain trust.",

        "payment manipulation":
            "The message attempts to influence the user into making a financial transaction.",

        "request for OTP or UPI PIN":
            "The message requests sensitive authentication information.",

        "fake refund scam":
            "The message uses a refund or cashback claim to encourage a suspicious payment.",

        "KYC or account blocking scam":
            "The message uses KYC or account-blocking pressure to make the user act."
    }

    for item in detected:
        explanations.append(
            explanation_map[item["category"]]
        )

    if not explanations:
        explanations.append(
            "No strong scam pattern was detected. However, always verify the sender before making a payment."
        )

    payment_info = extract_payment_info(text)

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "detected": detected,
        "explanations": explanations,
        "payment_info": payment_info
    }
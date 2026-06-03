import re
import logging

logger = logging.getLogger("LINK-NLP")

class NLPEngine:
    def __init__(self):
        try:
            import spacy
            # Loads the lightweight English dependency parser
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("[*] spaCy NLP intent engine online.")
        except ImportError:
            logger.warning("[!] spaCy engine missing. Run: pip install spacy && python -m spacy download en_core_web_sm")
            self.nlp = None
        except Exception as e:
            logger.warning(f"[!] spaCy engine load failed: {e}. Falling back to structural regex routing.")
            self.nlp = None

    def classify_intent(self, text: str) -> str:
        """Determines the exact system frame required before the LLM wakes up."""
        low_text = text.lower()

        # Air-Gapped Security Intercept (Hardcoded boundary)
        security_triggers = {"bypass", "override", "disable alarm", "unlock", "security override"}
        if any(trigger in low_text for trigger in security_triggers) and "lock" in low_text:
            return "SECURITY_BYPASS"

        # Triage Log Inspections (The Janitor Awareness)
        janitor_triggers = {"janitor", "overnight program", "maintenance log", "what happened overnight", "overnight clean", "morning report"}
        if any(trigger in low_text for trigger in janitor_triggers):
            return "JANITOR_REPORT"

        # Semantic Analysis via spaCy
        if self.nlp:
            doc = self.nlp(text)
            control_verbs = {"turn", "set", "open", "close", "toggle", "switch", "activate", "deactivate", "run", "dim", "brighten"}
            for token in doc:
                # If the root verb or its lemma indicates hardware manipulation
                if token.lemma_ in control_verbs or (token.pos_ == "VERB" and token.lemma_ in {"light", "plug", "power"}):
                    return "HOME_CONTROL"

        # Pure Regex Fallback for absolute resilience
        control_patterns = [r"\b(turn|set|switch|toggle|dim|brighten|open|close)\b", r"\b(on|off)\b"]
        if any(re.search(pat, low_text) for pat in control_patterns):
            return "HOME_CONTROL"

        # Default Fallback
        return "LORE_QUERY"
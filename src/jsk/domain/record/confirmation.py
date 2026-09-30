"""What a confirmation's quote has to share with the claim it confirms."""
import re

# A content word: four letters and longer. Shorter words are the connective tissue every
# sentence shares, and would let any quote "confirm" any claim.
WORD = re.compile(r"[a-z0-9]{4,}")

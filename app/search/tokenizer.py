"""Turn title/abstract text (or a query) into index terms.

Pipeline (Checkpoint B): drop $math$ and URLs -> unwrap LaTeX commands -> lowercase ->
split on non-alphanumerics (so hyphenated words split) -> drop pure numbers and
stopwords -> Porter stem. Queries go through the same function as documents.
"""

import re

from nltk.stem import PorterStemmer

_stemmer = PorterStemmer()

# NLTK's English stopword list, embedded so deploys don't need nltk.download().
STOPWORDS = frozenset(
    """
a about above after again against ain all am an and any are aren aren't as at be because been
before being below between both but by can couldn couldn't d did didn didn't do does doesn
doesn't doing don don't down during each few for from further had hadn hadn't has hasn hasn't
have haven haven't having he her here hers herself him himself his how i if in into is isn isn't
it it's its itself just ll m ma me mightn mightn't more most mustn mustn't my myself needn
needn't no nor not now o of off on once only or other our ours ourselves out over own re s same
shan shan't she she's should should've shouldn shouldn't so some such t than that that'll the
their theirs them themselves then there these they this those through to too under until up ve
very was wasn wasn't we were weren weren't what when where which while who whom why will with
won won't wouldn wouldn't y you you'd you'll you're you've your yours yourself yourselves
""".split()
)

_MATH = re.compile(r"\$\$.*?\$\$|\$[^$]*\$", re.DOTALL)  # display math first, then inline
_URL = re.compile(r"https?://\S+|www\.\S+")
_LATEX_DROP = re.compile(r"\\(?:cite\w*|ref|eqref|url|label)\{[^}]*\}")  # command + argument
_LATEX_CMD = re.compile(r"\\[a-zA-Z]+\*?")  # \emph{word} -> {word}; braces split away below
_TOKEN = re.compile(r"[a-z0-9]+")


def strip_markup(text: str) -> str:
    text = _MATH.sub(" ", text)
    text = _URL.sub(" ", text)
    text = _LATEX_DROP.sub(" ", text)
    return _LATEX_CMD.sub(" ", text)


def tokenize(text: str) -> list[str]:
    tokens = _TOKEN.findall(strip_markup(text).lower())
    return [
        _stemmer.stem(token) for token in tokens if not token.isdigit() and token not in STOPWORDS
    ]


if __name__ == "__main__":
    print(
        tokenize(
            r"We propose \emph{Retrieval-Augmented} agents for GPT-4 in $\mathbb{R}^d$ \cite{x}."
        )
    )

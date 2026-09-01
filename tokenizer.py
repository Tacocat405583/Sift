import re

from nltk.stem import PorterStemmer

_stemmer = PorterStemmer()


def tokenize(string: str) -> list[str]:    
    

    tokens = re.findall(r'[a-zA-Z0-9]+',string.lower())
    singles = [_stemmer.stem(token) for token in tokens]
    return singles




if __name__ == "__main__":
    result = tokenize("THE RED BLUE and hot fox, was here last at last night's gala, she was running")
    print(result)

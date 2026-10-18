"""Keep the method paper compact; preserve older scan appendix verbatim in SI."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];N=Path(__file__).parent
P=ROOT/'paper/innovation-addendum-v1.tex'

def main():
    s=P.read_text()
    if r'\section{Full removals, default scans and seed heterogeneity}' not in s:
        assert (N/'legacy-extended-appendix.tex').exists();return
    start=s.index(r'\section{Full removals, default scans and seed heterogeneity}')
    end=s.index(r'\section{Historical controls and reproducibility index}',start)
    legacy=s[start:end]
    (N/'legacy-extended-appendix.tex').write_text(legacy)
    (N/'before-layout-revision.tex').write_text(s)
    s=s[:start]+s[end:]
    s=s.replace(r'Appendix~\ref{app:extended}',r'Supplement~S7')
    assert 'app:extended' not in s
    s=s.replace(r'\begin{thebibliography}{99}',r'\begin{thebibliography}{99}\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}')
    P.write_text(s)

if __name__=='__main__':main()

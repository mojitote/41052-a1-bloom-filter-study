"""Create the report by patching the retained DOCX template, preserving opaque parts.
Usage: python scripts/build_report.py --template ../A1.docx
Requires python-docx's dependencies only indirectly: lxml and Pillow.
The original template is never overwritten. Its styles, footer and cover art stay intact.
"""
import argparse, copy, hashlib, json, math
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
S=json.loads((ROOT/'figures/summary.json').read_text())
def pick(section,**kw): return next(x for x in S[section] if all(x[k]==v for k,v in kw.items()))
def pct(v): return f'{v*100:.3f}%'
def ci(x,scale=1):return f'{x["mean"]*scale:.3f} ± {x["ci95_half"]*scale:.3f}'

# Page blocks keep figures next to the analysis they support. All substantive
# findings derive from the archived CSVs; personal understanding is not invented.
pages=[]
def page(title,items): pages.append((title,items))
def P(s):return ('p',s)
def H(s):return ('h',s)
def T(headers,rows):return ('table',headers,rows)
def F(name,caption):return ('figure',name,caption)

page('1 What I built',[
 P('This project implements an insertion-only Bloom filter in C++17 and studies the trade-off between accuracy, memory and query time. The main finding is that the parameter giving the lowest false-positive rate did not give the fastest exact lookup pipeline. A follow-up experiment also found that checking fewer bits could take longer than checking every bit.'),
 P('The filter stores unsigned 64-bit keys in a packed vector of 64-bit words. Its parameters are the number of bits m, the number of hash positions k and a seed. The public API provides insert and contains. A negative result is definite; a positive result means possibly present. Deletion, automatic resizing, persistence and concurrent mutation are outside the scope.'),
 P('Each position is produced with a separately salted SplitMix64 finalizer, then reduced modulo m. The mixer constants follow Vigna’s public-domain implementation [3]. These are deterministic, non-cryptographic hashes. Different salts do not prove independence. The study tests their behaviour on controlled inputs rather than claiming a universal hash guarantee.'),
 T(['Location','Purpose'],[['include/bloom.hpp','Packed storage, hashing and membership'],['src/study.cpp','Data generation, baselines and measurements'],['tests/test_bloom.cpp','Deterministic and randomized checks'],['src/early_exit.cpp','Follow-up early-exit ablation'],['scripts/analyze.py','Validation, summaries and plots']]),
])
page('1.1 Correctness and the difficult step',[
 P('The key invariant is that every bit required by an inserted key remains set. Initially all words are zero. Insertion visits the key’s k positions and uses bitwise OR to set each bit. OR preserves every previously set bit. Membership recomputes the same positions using the same m, k and seed. Therefore, every inserted key passes every check. This argument does not require the hashes to be independent.'),
 P('The word index is position / 64 and the bit offset is position % 64. UINT64_C(1) makes the mask unsigned and 64 bits wide; the offset is always between 0 and 63. This matters at word boundaries and for high bits. Storage rounds up to complete words without using an overflow-prone bits + 63 expression.'),
 P('The deterministic demo inserts 10, 20 and 30 into m = 64, k = 3, seed = 7. Key 10 uses positions 30, 14 and 16. The uninserted key 37 is reported present, demonstrating a legitimate false positive. A separate mutation demo replaces |= with = and makes an inserted key fail. This mutation is deliberately broken demonstration code, not a defect found in the main implementation.'),
 P('The final test suite passes 343,406 checks in both optimized and AddressSanitizer/UndefinedBehaviorSanitizer builds. It covers empty filters, invalid parameters, duplicate insertions, keys 0 and UINT64_MAX, word boundaries, saturation and exact-pipeline equivalence on each key. The accuracy study additionally checks 11,560,000 inserted-key memberships with zero false negatives. Tests support the argument above; they do not replace it.'),
])
page('2 Empirical study',[
 H('2.1 Questions and initial hypotheses'),
 P('The initial study had three questions. H1: at fixed bits per key, false-positive rates should follow the usual theoretical curve and have an interior minimum in k. H2: exceeding design capacity should increase false positives even though the implementation remains correct. H3: an exact pipeline with a Bloom prefilter should benefit mainly when queries are absent and the saved lookup cost exceeds the filter cost.'),
 P('For n distinct insertions into m bits, the probability that a bit remains unset under independent uniform hashing is (1 − 1/m)^(kn). The commonly used false-positive approximation is p ≈ (1 − exp(−kn/m))^k [1, 2]. It additionally approximates dependencies between queried bits. It is not an exact formula for this implementation.'),
 P('Writing b = m/n, minimizing this approximation gives k* ≈ b ln 2. At b = 10, k* ≈ 6.93, suggesting seven hashes. This minimizes the false-positive approximation at fixed storage, not wall-clock time or total system cost.'),
 T(['Experiment','Controlled design'],[['Hash sweep','n = 20,000; b ∈ {4, 8, 10, 16}; k = 1…16'],['Capacity','m = 200,000; k = 7; n = 5,000…60,000'],['Exact lookup','n ∈ {20,000, 200,000}; b = 10; k ∈ {1, 3, 7, 11}'],['Query mix','Absent fractions 0%, 50%, 90%, 100%']]),
])
page('2.2 Reproducible measurement',[
 P('Accuracy uses eight seeded filters and 200,000 absent queries per configuration. Keys are the bijective mix64 transform of consecutive counters. Disjoint counter ranges guarantee absent queries. Seeds change the ranges and hash salts; comparisons within a seed reuse keys. The 560 accuracy rows contain 112 million absent-query evaluations, not 112 million independent datasets.'),
 P('Timing uses four seeds, seven measured repetitions and 200,000 queries per repetition. Present queries sample inserted keys with replacement; absent queries are distinct. The mixture is shuffled. The three methods are an exact std::unordered_set, the approximate Bloom filter alone, and Bloom followed by the same exact set when needed. Only the first and third provide equivalent exact answers.'),
 P('Generation, allocation, construction, validation and printing are outside lookup timing. Each method is warmed up; execution order is shuffled per repetition. Returned counts are checked and consumed by an observable accumulator. The exact set is reserved at maximum load factor 1.0 and uses mix64. This is one standard-library baseline, not all hash tables.'),
 P('For each seed, timing is summarized by the median of seven repetitions. Plots show the mean of these seed medians and a two-sided Student t 95% interval across four seeds. Speedup is paired within seed before summarizing. Accuracy intervals use eight seed-level rates [4]. Repeated loops are not treated as independent trials. These descriptive intervals do not cover all machine or workload uncertainty.'),
])
a7=pick('accuracy',bits_per_key=10,k=7)
page('2.3 Accuracy and hash count',[
 F('accuracy.png','Figure 1. Left: eight-seed mean false-positive rates with 95% intervals and theoretical lines. Right: fixed-size filter loaded beyond design capacity. Some error bars are smaller than the markers.'),
 T(['Bits per key','Measured best k','FPR at that k'],[[str(b),str(int(min([x for x in S['accuracy'] if x['bits_per_key']==b],key=lambda x:x['mean'])['k'])),pct(min([x for x in S['accuracy'] if x['bits_per_key']==b],key=lambda x:x['mean'])['mean'])] for b in [4,8,10,16]]),
 P(f'At 10 bits per key, k = 7 gives {ci(a7,100)} percentage points, close to the theoretical 0.819%. Increasing k to 16 raises the measured rate to 2.714%. More positions must match, but inserting each key also sets more bits. Beyond the minimum, the increased occupancy outweighs the benefit of extra checks.'),
 P('At 16 bits per key, the smallest sample mean occurs at k = 12 rather than the rounded theoretical choice of 11. Nearby intervals overlap. This is not strong evidence that the theoretical optimum is wrong; selecting the smallest noisy estimate can move the apparent optimum. The curve and its uncertainty matter more than a single winning integer.'),
])
page('2.4 Capacity and storage',[
 T(['Inserted / design capacity','Measured false-positive rate'],[[f'{load:g}×',pct(pick('capacity',load=load)['mean'])] for load in [.5,1.,1.5,2.,3.]]),
 P('With m = 200,000 and k = 7, doubling the intended 20,000-key capacity raises false positives from 0.821% to 13.841%; tripling it raises them to 40.182%. Inserted keys still pass. This is saturation, not a correctness failure: design capacity is an accuracy budget rather than a hard insertion limit.'),
 P('At one quarter of capacity, only three false positives appear across 1.6 million absent-query evaluations. This is insufficient for a precise tail estimate. A near-zero observation does not prove that false positives are impossible.'),
 T(['Structure at n = 200,000','Requested storage'],[['Bloom bit array','250,000 bytes'],['Exact set nodes and buckets','6,400,024 bytes'],['Bloom plus exact set','6,650,024 bytes']]),
 P('Bloom-only storage is about 25.6 times smaller but gives approximate answers. The exact pipeline adds 250,000 bytes, about 3.9%. A counting allocator records requested set-node and bucket bytes; Bloom storage counts word payload. Object headers, allocator metadata and input vectors are excluded. These are structure-storage figures, not resident-memory measurements.'),
])
page('2.5 Exact lookup performance',[
 F('speedup.png','Figure 2. Exact set time divided by filtered-set time. Values above 1 favour the prefilter. Error bars are 95% intervals across four paired seed-level ratios.'),
 T(['n = 200,000','k = 1 speedup','k = 7 speedup'],[[f'{int(m*100)}% absent',ci(pick('speedup',n=200000,k=1,negative_fraction=m)),ci(pick('speedup',n=200000,k=7,negative_fraction=m))] for m in [0.,.5,.9,1.]]),
 P('The accuracy-optimal k = 7 did not reliably accelerate these in-memory lookups. For n = 20,000 and all-absent queries, its speedup is 0.713 ± 0.021, meaning a slowdown. In contrast, k = 1 gives 2.871 ± 0.357. Although one hash admits more false positives, it is cheaper and still rejects most absent keys.'),
 P('For n = 200,000 and all-absent queries, the k = 7 interval spans 1. The run is inconclusive about a speed advantage there. All-present workloads consistently penalize the prefilter because every query pays for both structures. A prefilter should be selected for the query mix and backend cost, not for low false-positive rate alone.'),
])
page('2.6 A follow-up on early exit',[
 F('early_exit.png','Figure 3. Follow-up ablation at k = 7. The early-exit and full-scan variants return identical results on every checked query. Bars show means of seed medians, with 95% intervals.'),
 P('The main run unexpectedly measured absent Bloom queries as slower than present queries. This motivated a separate, post-hoc experiment rather than a change to the original benchmark. It compares the core early-exit query with a diagnostic full scan over a reconstructed packed layout, using the same positions and contents. Each configuration has four seeds and seven timed repetitions. Source-level bit-probe counts are collected outside timing.'),
 P('At n = 200,000, an absent early-exit query checks about 1.996 positions on average but takes 41.69 ± 1.96 ns. The full scan checks all seven positions and takes 23.58 ± 0.50 ns. The smaller dataset shows the same direction. Fewer logical probes therefore do not imply lower elapsed time for this compiled implementation.'),
 P('The result is consistent with differences in branching and generated machine code. It does not isolate branch prediction: no branch counters or assembly analysis were collected, and the diagnostic layout has a different allocation address. Full scanning is a promising optimization to test in the exact pipeline, but that optimized pipeline has not been measured. The main results remain those of the original early-exit implementation.'),
])
page('2.7 Interpretation and limits',[
 P('Let q be the absent-query fraction and p the false-positive rate. The approximate backend-call fraction is r = (1 − q) + qp. Adding cost L per backend call gives Tset(L) = Tset(0) + L and Tfiltered(L) = Tfiltered(0) + rL. For r < 1, the break-even additional cost is L* = (Tfiltered(0) − Tset(0))/(1 − r).'),
 P('Using paired measurements at n = 20,000, k = 7 and all-absent queries gives L* between 11.18 and 12.17 ns across seeds. This is a derived threshold under a constant extra-cost assumption. It is not a database or network measurement; real backends can have batching, caching, concurrency and different hit/miss costs.'),
 P('The machine was an Apple M2 with 8 GB memory, macOS 14.4.1 and Apple Clang 15, using C++17 and -O3. CPU affinity, power state and background load were uncontrolled. Some intervals are wide. Warm queries, two set sizes and uniform integer keys do not represent cold storage, skew or adversarial inputs. The shared generator/filter mixer also limits independence conclusions.'),
 P('Construction times are separate single observations, excluded from query speedups. Each set-build time is repeated across k rows in the memory CSV, not independently remeasured. Recommendation: use about seven hashes for a 1% error target at 10 bits per key, but benchmark cheaper settings for exact in-memory throughput. Recheck capacity and workload assumptions.'),
])
page('3 What I learned',[
 H('3.1 The objective determines the parameter'),
 P('The most useful lesson is the difference between optimizing a component and optimizing the whole pipeline. Seven hashes gave a false-positive rate of 0.821%, whereas one hash gave 9.502%. However, for 200,000 keys and all-absent queries, the exact pipeline with one hash was about 2.71 times as fast as the direct set. The seven-hash pipeline had no clear speed advantage. Reducing false positives has value only in relation to the work avoided.'),
 H('3.2 Fewer operations can still take longer'),
 P('The early-exit experiment makes this lesson concrete. The absent-query path reduced the mean logical probes from seven to about two, yet the full scan was faster. Counting source-level operations is useful, but it leaves out how a processor executes branches and how a compiler transforms loops. The evidence supports a performance difference; it does not justify naming one hardware cause as proven.'),
 H('3.3 Correctness and usefulness are separate'),
 P('An overloaded Bloom filter can remain correct while becoming much less useful. At triple capacity it still produced no false negatives, but roughly 40% of absent queries passed. This changes how success should be defined: a test suite needs functional invariants, while the evaluation needs an accuracy target and an operating range. Merely showing that insert and contains run successfully would miss the main failure in usefulness.'),
])
page('3.4 Evidence changed the way results were judged',[
 P('The memory comparison also requires an explicit definition of what is being replaced. A 250,000-byte approximate filter and a 6,400,024-byte exact set answer different questions. Once the exact set is retained to verify positives, the filter increases total structure storage. The smaller number is useful only when its weaker guarantee fits the application.'),
 P('The apparent best hash count at 16 bits per key was another reminder to examine uncertainty. The measured minimum at 12 hashes is not automatically a new algorithmic discovery. Nearby choices have similar rates, and the minimum was selected from many estimates. Reporting the whole curve avoids making the conclusion depend on a noisy winner.'),
 P('Finally, test counts do not by themselves establish test independence. The first bit-vector oracle reused the filter’s position helper, so it could detect packing errors while sharing a hash-indexing error. Review led to fixed known-answer checks and per-key exact-pipeline checks. This gives stronger evidence, while still leaving the statistical quality of the salted hash family as an assumption rather than a proof.'),
 P('These are evidence-based lessons from the project, not claims that every implementation detail has been independently mastered. The required spoken walkthrough should demonstrate the insertion invariant, bit indexing and the |= mutation directly in the code. The distinction matters because an AI-assisted report can be more polished than the author’s current understanding.'),
])
page('4 AI use',[
 P('I used OpenAI Codex extensively for topic selection, implementation, tests, experimental design and execution, analysis, documentation and report drafting. It also adapted the Word template and uploaded the repository. Most code and report text were AI-generated; I do not claim to have independently written every line or run every command.'),
 P('The first generated reference test reused BloomFilter::position. It checked packed storage but could share an indexing bug. AI-assisted review added fixed mixer/index vectors and per-key equality between the exact pipeline and the set. The initial version is preserved in commit 93063ae; the correction is visible in the test diff.'),
 P('The analysis script also assumed SciPy and Matplotlib were installed. Execution failed with ModuleNotFoundError for scipy, then matplotlib. The fix used explicit t critical values for the supported seed counts and installed plotting dependencies locally. Commands, package versions and successful output are recorded. The raw measurements were unchanged.'),
 P('Agent verification includes compilation, tests, sanitizers, CSV checks and figure regeneration. It does not establish my personal understanding. Hash independence and the hardware cause of the timing results remain unproven. I need to demonstrate the code explanations myself in the walkthrough. The deliberate |= mutation is an educational example, not an accidental AI bug.'),
])
page('References',[
 P('[1] Bloom, B. H. (1970). Space/time trade-offs in hash coding with allowable errors. Communications of the ACM, 13(7), 422–426. https://doi.org/10.1145/362686.362692'),
 P('[2] Kirsch, A., Mitzenmacher, M., and Varghese, G. Hash-based techniques for high-speed packet processing. Author manuscript. https://www.eecs.harvard.edu/~michaelm/postscripts/dimacs-chapter-08.pdf'),
 P('[3] Vigna, S. (2015). splitmix64.c. Public-domain reference implementation. https://prng.di.unimi.it/splitmix64.c'),
 P('[4] NIST/SEMATECH. e-Handbook of Statistical Methods, section 1.3.6.7.2: Critical values of the Student’s t distribution. https://www.itl.nist.gov/div898/handbook/eda/section3/eda3672.htm'),
 H('Reproduction record'),
 P('Repository: https://github.com/mojitote/41052-a1-bloom-filter-study. Main data: results/full-20260910/. Follow-up data: results/early-exit-20260910.csv. Machine, compiler and source fingerprints: results/environment.json. Exact commands and dependency setup: README.md. Numerical tables and figure source: figures/ and scripts/analyze.py. All external sources accessed on 10 September 2026.'),
])

W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS={'w':W,'r':R}
def el(tag,**attrs):return E.Element('{'+W+'}'+tag,{'{'+W+'}'+k:str(v) for k,v in attrs.items()})
def text_run(text,bold=False,size=None,color=None):
    r=el('r')
    if bold or size or color:
        pr=el('rPr');r.append(pr)
        if bold:pr.append(el('b'))
        if size:pr.append(el('sz',val=size*2))
        if color:pr.append(el('color',val=color))
    t=el('t');t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=text;r.append(t);return r
def para(text='',style='Normal',page_break=False,compact=False,bookmark=None):
    p=el('p');pr=el('pPr');p.append(pr);pr.append(el('pStyle',val=style))
    if style.startswith('Heading'):
        num=el('numPr');num.append(el('numId',val=0));pr.append(num);pr.append(el('ind',left=0,hanging=0))
    if page_break:pr.append(el('pageBreakBefore'))
    if compact:pr.append(el('spacing',after=100,line=240,lineRule='auto'))
    if bookmark:
        p.append(el('bookmarkStart',id=bookmark[0],name=bookmark[1]))
    p.append(text_run(text))
    if bookmark:p.append(el('bookmarkEnd',id=bookmark[0]))
    return p
def table(headers,rows):
    tbl=el('tbl');pr=el('tblPr');tbl.append(pr);pr.append(el('tblW',w=8500,type='dxa'))
    borders=el('tblBorders');pr.append(borders)
    for name in ['top','left','bottom','right','insideH','insideV']:borders.append(el(name,val='single',sz=4,color='D9D9D9'))
    widths=[int(8500/len(headers))]*len(headers)
    if len(headers)==2:widths=[3800,4700]
    grid=el('tblGrid');tbl.append(grid)
    for w in widths:grid.append(el('gridCol',w=w))
    for i,row in enumerate([headers]+rows):
        tr=el('tr');tbl.append(tr);rp=el('trPr');tr.append(rp);rp.append(el('cantSplit'))
        if i==0:rp.append(el('tblHeader'))
        for j,value in enumerate(row):
            tc=el('tc');tr.append(tc);cp=el('tcPr');tc.append(cp);cp.append(el('tcW',w=widths[j],type='dxa'));cp.append(el('vAlign',val='center'))
            cp.append(el('shd',fill='1F497D' if i==0 else ('F1F4F7' if i%2 else 'FFFFFF')))
            margins=el('tcMar');cp.append(margins)
            for side in ['top','left','bottom','right']:margins.append(el(side,w=90,type='dxa'))
            pp=para('',compact=True);pp.remove(pp[-1]);pp.append(text_run(str(value),bold=i==0,size=10,color='FFFFFF' if i==0 else '000000'));tc.append(pp)
    return tbl
def figure(path,rid,idx):
    w,h=Image.open(path).size;cx=5350000;cy=int(cx*h/w)
    xml=f'''<w:p xmlns:w="{W}" xmlns:r="{R}" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><w:pPr><w:keepNext/><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{100+idx}" name="Study figure {idx}"/><wp:cNvGraphicFramePr/><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="{path.name}"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'''
    return E.fromstring(xml.encode())

def main():
    p=argparse.ArgumentParser();p.add_argument('--template',type=Path,required=True);p.add_argument('--out',type=Path,default=ROOT/'docs/Bloom_Filter_Report.docx');args=p.parse_args()
    original=args.template.read_bytes();parts={}
    with ZipFile(args.template) as z:
        infos=z.infolist();parts={i.filename:z.read(i.filename) for i in infos}
    doc=E.fromstring(parts['word/document.xml']);body=doc.find('w:body',NS)
    cover=copy.deepcopy(body[0]);sect=copy.deepcopy(body[-1])
    runs=cover.findall('w:r',NS)
    runs[0].find('w:t',NS).text='41052 Advanced Algorithms'
    runs[2].find('w:t',NS).text='Bloom filters in practice'
    runs[3].find('w:t',NS).text=''
    # Keep all anchored drawings, shape metadata and the cover section break.
    for c in list(body):body.remove(c)
    body.append(cover)
    body.append(para('Table of Contents','Heading1'))
    for i,(title,_) in enumerate(pages):
        pp=para('',style='TOC1',compact=True);pp.remove(pp[-1])
        tabs=el('tabs');tabs.append(el('tab',val='right',pos=8500,leader='dot'));pp[0].append(tabs)
        link=el('hyperlink',anchor=f'study_{i}');link.append(text_run(title));pp.append(link)
        tr=el('r');tr.append(el('tab'));pp.append(tr)
        fld=el('fldSimple',instr=f' PAGEREF study_{i} \\h ');fld.append(text_run(str(i+3)));pp.append(fld);body.append(pp)
    rel=E.fromstring(parts['word/_rels/document.xml.rels']);rel_ns='http://schemas.openxmlformats.org/package/2006/relationships';added={};md=[];figure_idx=0
    for i,(title,items) in enumerate(pages):
        style='Heading1' if title in ['1 What I built','2 Empirical study','3 What I learned','4 AI use','References'] else 'Heading2'
        body.append(para(title,style,page_break=True,bookmark=(3000+i,f'study_{i}')));md.append('## '+title+'\n')
        for item in items:
            if item[0]=='p':
                pp=para(item[1])
                if E.QName(body[-1]).localname=='tbl':pp[0].append(el('spacing',before=140))
                body.append(pp);md.append(item[1]+'\n')
            if item[0]=='h':body.append(para(item[1],'Heading2'));md.append('### '+item[1]+'\n')
            if item[0]=='table':
                body.append(table(item[1],item[2]));md.extend(['| '+' | '.join(item[1])+' |','| '+' | '.join(['---']*len(item[1]))+' |']+['| '+' | '.join(map(str,r))+' |' for r in item[2]]+[''])
            if item[0]=='figure':
                figure_idx+=1;rid=f'rIdStudy{figure_idx}';path=ROOT/'figures'/item[1];target=f'media/study{figure_idx}.png'
                rr=E.SubElement(rel,'{'+rel_ns+'}Relationship');rr.set('Id',rid);rr.set('Type',R+'/image');rr.set('Target',target)
                added['word/'+target]=path.read_bytes();body.append(figure(path,rid,figure_idx))
                cap=para('',compact=True);cap.remove(cap[-1]);cap.append(text_run(item[2],size=10));body.append(cap)
                md.append(f'![{item[2]}](../figures/{item[1]})\n')
    body.append(sect)
    settings=E.fromstring(parts['word/settings.xml']);u=settings.find('w:updateFields',NS)
    if u is None:u=el('updateFields');settings.append(u)
    u.set('{'+W+'}val','true')
    serialize=lambda x:E.tostring(x,encoding='UTF-8',xml_declaration=True,standalone=True)
    replacements={'word/document.xml':serialize(doc),'word/_rels/document.xml.rels':serialize(rel),'word/settings.xml':serialize(settings)}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(args.out,'w',ZIP_DEFLATED) as z:
        for info in infos:z.writestr(info,replacements.get(info.filename,parts[info.filename]))
        for name,data in added.items():z.writestr(name,data)
    with ZipFile(args.out) as z:
        unchanged=[name for name in parts if name not in replacements]
        assert all(z.read(name)==parts[name] for name in unchanged)
    assert args.template.read_bytes()==original
    (ROOT/'docs/report.md').write_text(('# Bloom filters in practice\n\n'+ '\n'.join(md)).rstrip()+'\n')
    (ROOT/'docs/template_fidelity.json').write_text(json.dumps({'reference_sha256':hashlib.sha256(original).hexdigest(),'modified_parts':list(replacements),'added_figures':list(added),'preserved_original_parts':len(unchanged),'sections':2,'planned_pages':len(pages)+2},indent=2)+'\n')
    print(f'Created {args.out}; {len(pages)+2} planned pages; {len(unchanged)} original package parts unchanged.')

if __name__=='__main__':main()

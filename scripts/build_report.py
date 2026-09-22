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
U=json.loads((ROOT/'figures/pipeline_summary.json').read_text())
def up(n,k,q): return next(x for x in U if x['n']==n and x['k']==k and x['negative_fraction']==q)
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
 P('This project uses C++17 to implement a Bloom filter that supports insertion and lookup. The experiments compare its error rate, memory use and query time. The main finding is that fewer false positives do not always mean faster queries. With many queries for missing keys, using one hash was faster than using seven, even though seven gave a lower error rate.'),
 P('The filter takes unsigned 64-bit keys as input and stores their bit markers in an array of 64-bit words. Its settings are the number of bits m, the number of hashes k and a seed. insert sets the markers; contains returns false for definitely absent and true for possibly present. The implementation does not support deletion, resizing, saving to disk or concurrent updates.'),
 P('To calculate each position, the code mixes the key with a salt that depends on the seed and hash number, then takes the result modulo m. It uses the SplitMix64 finalizer and constants from Vigna [3]. This is a deterministic, non-cryptographic hash. Using different salts does not prove that the hash positions are independent.'),
 T(['Location','Purpose'],[['include/bloom.hpp','Packed storage, hashing and membership'],['src/study.cpp','Data generation, baselines and measurements'],['tests/test_bloom.cpp','Deterministic and randomized checks'],['src/pipeline_exit.cpp','Paired exact-pipeline follow-up'],['scripts/analyze*.py','Validation, summaries and plots']]),
])
page('1.1 Correctness and the difficult step',[
 P('The invariant is that every bit needed by an inserted key stays set. All bits start at zero. Insertion uses bitwise OR to set the key’s k positions without clearing existing bits. Lookup checks the same positions with the same settings. Therefore, an inserted key always returns true. This guarantee holds even if the hashes are not independent.'),
 P('For a position p, p / 64 selects the word and p % 64 selects the bit inside it. UINT64_C(1) provides an unsigned constant wide enough to shift to any bit in a word. The offset stays between 0 and 63. The allocation rounds up to whole words and avoids adding 63 to bits, which could overflow for a very large input.'),
 P('The demo uses m = 64, k = 3 and seed = 7, then inserts 10, 20 and 30. Key 10 uses positions 30, 14 and 16. Key 37 also returns true although it was never inserted: this is a false positive. A separate, deliberately broken example replaces |= with =. This clears earlier bits in the word and causes an inserted key to return false.'),
 P('The tests pass 464,427 checks in both the optimised build and the AddressSanitizer/UndefinedBehaviorSanitizer build. They cover empty filters, invalid settings, repeated insertions, keys 0 and UINT64_MAX, word boundaries and full filters. They also check that both query versions agree and that the filter followed by an exact set gives the correct answer for each tested key. The accuracy experiment checks another 11,560,000 inserted-key lookups with no false negatives.'),
])
page('2 Empirical study',[
 H('2.1 Questions and initial hypotheses'),
 P('The study began with three hypotheses. H1: with a fixed number of bits per key, increasing k should first lower the false-positive rate and then raise it, following the theoretical curve. H2: inserting more keys than the filter was designed for should increase false positives without causing false negatives. H3: filtering before an exact lookup should help when it rejects enough missing keys to save more time than the filter takes.'),
 P('For n distinct keys in m bits, independent uniform hashing gives a probability of (1 − 1/m)^(kn) that a bit stays zero. The usual approximation for the false-positive rate is p ≈ (1 − exp(−kn/m))^k [1, 2]. It treats the queried bit values as approximately independent, so it predicts the rate rather than giving an exact value for this implementation.'),
 P('Let b = m/n be the average bit budget per key. The hash count that minimises the approximate false-positive rate is k* ≈ b ln 2. With b = 10, this gives k* ≈ 6.93, so seven hashes are a reasonable choice for accuracy. The formula does not include the time spent calculating and checking those hashes.'),
 T(['Experiment','Controlled design'],[['Hash sweep','n = 20,000; b ∈ {4, 8, 10, 16}; k = 1…16'],['Capacity','m = 200,000; k = 7; n = 5,000…60,000'],['Exact lookup','n ∈ {20,000, 200,000}; b = 10; k ∈ {1, 3, 7, 11}'],['Query mix','Absent fractions 0%, 50%, 90%, 100%']]),
])
page('2.2 Reproducible measurement',[
 P('Each accuracy setting uses eight seeds and 200,000 absent queries. Applying the one-to-one mix64 mapping to separate counter ranges keeps inserted and absent keys distinct. Seeds change the ranges and salts; comparisons within a seed reuse keys. The 560 rows record 112 million query evaluations.'),
 P('Timing uses four seeds, seven repetitions and 200,000 queries per repetition. Present keys are sampled with replacement; absent keys are distinct. Queries are shuffled. The methods are std::unordered_set alone, Bloom alone, and Bloom followed by the set for possible matches. This last method is the exact pipeline: the set verifies matches, keeping the final answer exact.'),
 P('Only lookup is timed. Generation, allocation, construction, validation and printing are excluded. Methods are warmed up and randomly ordered in each repetition. Counts are checked and added to an observable accumulator so the compiler cannot discard the queries. The set uses mix64, reserves space for n keys and has maximum load factor 1.0.'),
 P('For each seed, the analysis takes the median of seven timings, then reports the mean of the four medians and a two-sided Student t 95% interval. Speedup is calculated within each seed before averaging. Accuracy intervals use eight seed-level rates [4]. Repetitions are not independent samples. The intervals describe seed variation, not all machine or workload uncertainty.'),
])
a7=pick('accuracy',bits_per_key=10,k=7)
page('2.3 Accuracy and hash count',[
 F('accuracy.png','Figure 1. Left: mean false-positive rates across eight seeds, with 95% intervals and theoretical curves. Right: the effect of inserting more keys into a fixed-size filter. Some error bars are too small to see.'),
 T(['Bits per key','Measured best k','FPR at that k'],[[str(b),str(int(min([x for x in S['accuracy'] if x['bits_per_key']==b],key=lambda x:x['mean'])['k'])),pct(min([x for x in S['accuracy'] if x['bits_per_key']==b],key=lambda x:x['mean'])['mean'])] for b in [4,8,10,16]]),
 P('At 10 bits per key, k = 7 gives a false-positive rate of {value} percentage points, close to the predicted 0.819%. Raising k to 16 increases the measured rate to 2.714%. More hashes make a query check more positions, but they also set more bits during insertion. When the array becomes too full, the extra checks no longer reduce false positives.'.format(value=ci(a7,100))),
 P('At 16 bits per key, k = 12 has the lowest measured mean, while the rounded theoretical choice is 11. The confidence intervals for nearby choices overlap, so the result does not clearly show that 12 is better. Random variation can change which setting has the smallest measured value.'),
])
page('2.4 Capacity and storage',[
 T(['Inserted / design capacity','Measured false-positive rate'],[[f'{load:g}×',pct(pick('capacity',load=load)['mean'])] for load in [.5,1.,1.5,2.,3.]]),
 P('With m = 200,000 and k = 7, the filter was designed for 20,000 keys. At twice that capacity, false positives rise from 0.821% to 13.841%; at three times capacity, they reach 40.182%. Inserted keys still pass, but the fuller array rejects fewer absent keys.'),
 P('At one quarter of capacity, only three false positives occurred in 1.6 million absent queries. There are too few errors to estimate this small probability precisely.'),
 T(['Structure at n = 200,000','Requested storage'],[['Bloom bit array','250,000 bytes'],['Exact set nodes and buckets','6,400,024 bytes'],['Bloom plus exact set','6,650,024 bytes']]),
 P('The exact set uses about 25.6 times the storage of the filter, but gives exact answers. Adding the filter to the set costs another 250,000 bytes, or 3.9%. Measurements count requested set-node and bucket bytes and the filter’s word array. They exclude object headers, allocator metadata and input vectors, rather than measuring total process memory.'),
])
page('2.5 Exact lookup performance',[
 F('speedup.png','Figure 2. Set-only query time divided by filter-plus-set query time. A value above 1 means the filter speeds up exact lookup. Error bars show 95% intervals across four paired seed ratios.'),
 T(['n = 200,000','k = 1 speedup','k = 7 speedup'],[[f'{int(m*100)}% absent',ci(pick('speedup',n=200000,k=1,negative_fraction=m)),ci(pick('speedup',n=200000,k=7,negative_fraction=m))] for m in [0.,.5,.9,1.]]),
 P('Seven hashes gave a low error rate but did not consistently make exact lookup faster. With 20,000 keys and all queries absent, its speedup was 0.713 ± 0.021, meaning it was slower than the set alone. One hash gave 2.871 ± 0.357. Although it allowed more false positives, it took less time to check and still rejected most absent keys.'),
 P('With 200,000 keys and all queries absent, the interval for k = 7 includes 1, so this run does not clearly show a speed advantage. When all queried keys were present, adding the filter always made lookup slower because every query still reached the set. The benefit depends on the proportion of absent queries and the cost of checking the set.'),
])
page('2.6 A follow-up on early exit',[
 F('early_exit.png','Figure 3. Early exit compared with full scanning at k = 7. Both give the same result for every checked query. Bars show the mean of the seed medians, with 95% intervals.'),
 P('In the main experiment, Bloom queries for absent keys took longer than queries for present keys, even though they could stop early. A separate experiment compared early exit with a version that checks all k positions, called a full scan. The full scan used a separate word array with the same contents and positions. Each setting used four seeds and seven timed repetitions. Bit checks were counted outside timing.'),
 P('With n = 200,000, early exit checked about 1.996 positions per absent query and took 41.69 ± 1.96 ns. Full scanning checked all seven positions but took only 23.58 ± 0.50 ns. The smaller dataset showed the same pattern. In these tests, checking fewer bits did not make the query faster.'),
 P('Branches and compiler-generated code may explain the difference, but no branch counters or assembly analysis were collected. The two arrays also had different memory addresses. The next experiment removes that storage difference and compares both versions as part of exact lookup. Its timings are reported separately from this run.'),
])
page('2.7 Full scanning in the exact pipeline',[
 F('pipeline_exit.png','Figure 4. The September 22 comparison of both exact pipelines. Values above 1 mean faster lookup than the set alone. Error bars show 95% intervals across four seed ratios.'),
 P('The next experiment uses contains and contains_full_scan on the same Bloom object, followed by the same exact set. Both versions read the same bits and send the same queries to the set. Full scanning uses &= to combine all bit checks without an early return. Before timing, both versions are checked against the exact set for every query.'),
 P('The experiment uses two set sizes, k = 1 or 7, four absent-query proportions and four seeds. Each method has seven repetitions of 200,000 queries, giving 1,344 timing rows. Data generation and validation stay outside timing. Methods are warmed up and run in random order. Analysis uses the same seed-median and paired-ratio method as before. With k = 1, both query versions check just one bit, providing a useful control.'),
 T(['n = 200,000; k = 7','Set / early time','Set / full time'],[[f'{int(q*100)}% absent',ci(up(200000,7,q)['early_speedup']),ci(up(200000,7,q)['full_speedup'])] for q in [.5,.9,1.]]),
])
page('2.7.1 Results and scope',[
 P('With 200,000 keys, k = 7 and all queries absent, full scanning makes the exact pipeline {ratio} times as fast as early exit. Compared with the set alone, the speedup is {full} for full scanning and {early} for early exit. Full scanning therefore improves the whole lookup process in this setting, not only the filter by itself.'.format(ratio=ci(up(200000,7,1.)['full_over_early']), full=ci(up(200000,7,1.)['full_speedup']), early=ci(up(200000,7,1.)['early_speedup']))),
 P('The result changes with the queries. When half are absent, the full-scan/early-exit speed ratio is {ratio}, so full scanning is slower. With 90% absent queries, its speedup over the set alone is {speedup}. That interval includes 1, so there is no clear advantage over the set in this case.'.format(ratio=ci(up(200000,7,.5)['full_over_early']), speedup=ci(up(200000,7,.9)['full_speedup']))),
 P('For the smaller set, full scanning with k = 7 also helps when all queries are absent: its speedup over the set alone is {small}. However, one hash with early exit remains faster in the 200,000-key, all-absent test, with a speedup of {one}. Improving the seven-hash version does not make it the fastest tested setting.'.format(small=ci(up(20000,7,1.)['full_speedup']), one=ci(up(200000,1,1.)['early_speedup']))),
 P('Using one Bloom object removes the different array addresses from the earlier comparison. With k = 1, the timing differences between versions are much smaller than with k = 7 when most queries are absent. However, the experiment does not separate the effects of branches, vectorisation or instruction scheduling. It uses four seeds, a fixed order of configurations and an active desktop machine.'),
])
page('2.8 Interpretation and limits',[
 P('Let q be the fraction of queries for absent keys and p the false-positive rate. The fraction reaching the exact set is approximately r = (1 − q) + qp: all present keys and the false positives need an exact check. If each set lookup costs an extra L, then Tset(L) = Tset(0) + L and Tfiltered(L) = Tfiltered(0) + rL. For r < 1, the extra cost at which the methods take equal time is L* = (Tfiltered(0) − Tset(0))/(1 − r).'),
 P('For n = 20,000, k = 7 and all queries absent, the original paired timings give L* values between 11.18 and 12.17 ns across seeds. This estimates how much extra lookup cost would make filtering worthwhile. It assumes the same extra cost for every set lookup; real databases or networks may behave differently because of caching, batching, concurrency and different costs for hits and misses.'),
 P('Both runs used an Apple M2 with 8 GB memory, macOS 14.4.1 and Apple Clang 15, compiling C++17 with -O3. CPU affinity, power state and background activity were not controlled. The tests use warmed-up queries, two set sizes and uniform integer keys. They do not cover cold storage, skewed queries or adversarial inputs. Data generation and filtering also share the same mixer family.'),
 P('Construction was measured separately and is excluded from query speedups. Each set-build time is one observation copied across the relevant k rows in the memory CSV, not a new measurement in each row. The performance comparison therefore concerns repeated lookups after the structures have been built.'),
])
page('2.9 Choosing a configuration',[
 P('Choose the setting based on the answer guarantee and the work it needs to save. If false positives are acceptable, select m and k for the error target. If answers must be exact, keep the set and measure the combined query time. In that case, the filter uses extra memory to avoid some set lookups.'),
 T(['Goal or workload','Recommendation within tested scope'],[
 ['About 1% false positives at 10 bits/key','Use about 7 hashes at design capacity. Check how full the array becomes as more keys are inserted.'],
 ['Faster exact lookup with 90–100% absent queries','Test fewer hashes first. In the follow-up, k = 1 was faster than k = 7.'],
 ['All queries present','Use the set directly for these tested workloads. The filter did not avoid any set lookups.'],
 ['k = 7 required, all queries absent','Test full scanning. It improved exact lookup at both tested set sizes.'],
 ['Mixed queries or another backend','Compare both versions with the set alone. Early exit was faster than full scanning at 50% absent.']]),
 P('These recommendations apply to the tested C++17 code and integer queries. A more expensive exact lookup may make stronger filtering worthwhile. Changes in capacity, query distribution, compiler or machine need new measurements. Alternative mixer constants were not compared, so the study does not establish that the chosen constants are best.'),
])
page('3 What I learned',[
 H('3.1 The objective determines the parameter'),
 P('I learned to separate low error from fast exact lookup. Seven hashes gave 0.821% false positives, compared with 9.502% for one hash. However, with 200,000 keys and all queries absent, the one-hash exact pipeline was about 2.71 times as fast as the set alone. The original seven-hash early-exit version showed no clear speed advantage. Extra filtering is useful only when the lookups it avoids save enough time to pay for it.'),
 H('3.2 Fewer operations can still take longer'),
 P('The early-exit result showed why counting operations is not enough to predict runtime. It checked about two bits on average, yet checking all seven was faster. The later exact-pipeline test also showed that full scanning helped when all queries were absent but lost to early exit when half were absent. This makes workload testing necessary; the code with fewer checks is not automatically the faster choice.'),
 H('3.3 Correctness and usefulness are separate'),
 P('I also learned that a correct filter can become less useful. At three times its design capacity, it still had no false negatives, but about 40% of absent queries passed through. Correctness tests need to check that inserted keys are never rejected. Performance tests also need to check whether the error rate is acceptable at the intended capacity.'),
])
page('3.4 Evidence changed the way results were judged',[
 P('The memory comparison taught me to check what each structure provides. The filter used 250,000 bytes and the exact set used 6,400,024 bytes, but they offered different answer guarantees. Keeping the exact set to check possible matches increased total storage. The small filter only replaces the set when false positives are acceptable.'),
 P('The hash-count results also showed why I should consider uncertainty. At 16 bits per key, 12 hashes had the lowest measured error rate, but nearby settings had overlapping intervals. I cannot conclude that 12 is truly better from that minimum alone. The full curve gives a clearer picture than naming one setting as the winner.'),
 P('Finally, many passing checks are not enough if the test repeats the same mistake as the implementation. The first reference bit array reused position(), so it could detect storage errors but miss an error in position(). Review added fixed expected values and checked the exact pipeline against the set for each key. Those checks strengthen correctness evidence, while hash distribution still needs separate evaluation.'),
])
page('4 AI use',[
 P('I used OpenAI Codex for most of the code and report, including implementation, debugging, tests, experiment design, running measurements, analysis and drafting. It also adapted the Word template and uploaded the repository. The September 22 revision used Codex to add full scanning, compare the two exact pipelines and update the recommendations.'),
 P('One problem was that the first generated reference test reused BloomFilter::position. If that function was wrong, the test could repeat the same error. AI-assisted review added fixed expected mixer outputs and positions, plus checks that the exact pipeline and set agreed on each key. Commit 93063ae contains the initial version, and the test diff records the changes.'),
 P('Another problem was that the generated analysis script assumed SciPy and Matplotlib were installed. It failed with ModuleNotFoundError for scipy and then matplotlib. The fix replaced the SciPy dependency with explicit t critical values for the supported seed counts and installed the plotting dependencies locally. The commands and successful output were recorded; the raw measurements stayed unchanged.'),
 P('Codex ran the builds, tests, sanitizers, CSV checks and plot generation. I worked through the bit indexing, insertion invariant and query logic during code review. I relied on the published mixer constants rather than deriving them. Hash independence and the hardware cause of the timing results remain unproven. The |= to = example was deliberately written to show a failure, rather than being an accidental AI bug.'),
])
page('References',[
 P('[1] Bloom, B. H. (1970). Space/time trade-offs in hash coding with allowable errors. Communications of the ACM, 13(7), 422–426. https://doi.org/10.1145/362686.362692'),
 P('[2] Kirsch, A., Mitzenmacher, M., and Varghese, G. Hash-based techniques for high-speed packet processing. Author manuscript. https://www.eecs.harvard.edu/~michaelm/postscripts/dimacs-chapter-08.pdf'),
 P('[3] Vigna, S. (2015). splitmix64.c. Public-domain reference implementation. https://prng.di.unimi.it/splitmix64.c'),
 P('[4] NIST/SEMATECH. e-Handbook of Statistical Methods, section 1.3.6.7.2: Critical values of the Student’s t distribution. https://www.itl.nist.gov/div898/handbook/eda/section3/eda3672.htm'),
 H('Reproduction record'),
 P('Repository: https://github.com/mojitote/41052-a1-bloom-filter-study. Main data: results/full-20260910/. Follow-up data: results/early-exit-20260910.csv. New exact-pipeline data: results/pipeline-exit-20260922.csv; analysis: scripts/analyze_pipeline.py. Original environment: results/environment.json; revision metadata: results/upgrade-environment-20260922.json. Exact commands and dependency setup: README.md. Numerical tables and figure source: figures/ and scripts/analyze.py. All external sources accessed on 10 September 2026.'),
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
    p=argparse.ArgumentParser();p.add_argument('--template',type=Path,required=True);p.add_argument('--out',type=Path,default=ROOT/'docs/Bloom_Filter_Report_Optimized.docx');args=p.parse_args()
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
    if args.out.resolve() == (ROOT/'docs/Bloom_Filter_Report_Optimized.docx').resolve():
        (ROOT/'docs/Bloom_Filter_Report.docx').write_bytes(args.out.read_bytes())
    print(f'Created {args.out}; {len(pages)+2} planned pages; {len(unchanged)} original package parts unchanged.')

if __name__=='__main__':main()

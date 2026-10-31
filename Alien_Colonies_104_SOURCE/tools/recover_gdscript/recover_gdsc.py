"""Recover readable GDScript from unencrypted Godot 4.5.1 GDSC 101.

Validation is token/layout comparison by a local lexical checker, not a Godot
compiler or runtime test. Source comments cannot be recovered from bytecode.
"""
from __future__ import annotations
import ast
import json
import math
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'tools'))
import gdsc_tools

TOKEN_NAMES = '''EMPTY ANNOTATION IDENTIFIER LITERAL LESS LESS_EQUAL GREATER GREATER_EQUAL EQUAL_EQUAL BANG_EQUAL AND OR NOT AMPERSAND_AMPERSAND PIPE_PIPE BANG AMPERSAND PIPE TILDE CARET LESS_LESS GREATER_GREATER PLUS MINUS STAR STAR_STAR SLASH PERCENT EQUAL PLUS_EQUAL MINUS_EQUAL STAR_EQUAL STAR_STAR_EQUAL SLASH_EQUAL PERCENT_EQUAL LESS_LESS_EQUAL GREATER_GREATER_EQUAL AMPERSAND_EQUAL PIPE_EQUAL CARET_EQUAL IF ELIF ELSE FOR WHILE BREAK CONTINUE PASS RETURN MATCH WHEN AS ASSERT AWAIT BREAKPOINT CLASS CLASS_NAME TK_CONST ENUM EXTENDS FUNC TK_IN IS NAMESPACE PRELOAD SELF SIGNAL STATIC SUPER TRAIT VAR TK_VOID YIELD BRACKET_OPEN BRACKET_CLOSE BRACE_OPEN BRACE_CLOSE PARENTHESIS_OPEN PARENTHESIS_CLOSE COMMA SEMICOLON PERIOD PERIOD_PERIOD PERIOD_PERIOD_PERIOD COLON DOLLAR FORWARD_ARROW UNDERSCORE NEWLINE INDENT DEDENT CONST_PI CONST_TAU CONST_INF CONST_NAN VCS_CONFLICT_MARKER BACKTICK QUESTION_MARK ERROR TK_EOF TK_MAX'''.split()
SPELL = {
 4:'<',5:'<=',6:'>',7:'>=',8:'==',9:'!=',10:'and',11:'or',12:'not',
 13:'&&',14:'||',15:'!',16:'&',17:'|',18:'~',19:'^',20:'<<',21:'>>',
 22:'+',23:'-',24:'*',25:'**',26:'/',27:'%',28:'=',29:'+=',30:'-=',31:'*=',
 32:'**=',33:'/=',34:'%=',35:'<<=',36:'>>=',37:'&=',38:'|=',39:'^=',
 73:'[',74:']',75:'{',76:'}',77:'(',78:')',79:',',80:';',81:'.',82:'..',
 83:'...',84:':',85:'$',86:'->',87:'_',91:'PI',92:'TAU',93:'INF',94:'NAN',
 96:'`',97:'?'
}
for _index in range(40,73):
    SPELL[_index] = TOKEN_NAMES[_index].removeprefix('TK_').lower()
KEYWORDS = {v:(k,) for k,v in SPELL.items() if v.isidentifier()}
OPS = sorted(((v,k) for k,v in SPELL.items() if not v.isidentifier()), key=lambda x: -len(x[0]))
IDENT = re.compile(r'[^\W\d]\w*', re.UNICODE)
NUMBER = re.compile(r'(?:0[xX][0-9A-Fa-f_]+|0[bB][01_]+|(?:\d[\d_]*(?:\.[\d_]*)?|\.\d[\d_]*)(?:[eE][+-]?[\d_]+)?)')


def literal_text(pair):
    kind,value=pair
    if kind == 0:return 'null'
    if kind == 1:return 'true' if value else 'false'
    if kind == 2:return str(value)
    if kind == 3:
        value=float.fromhex(value)
        if not math.isfinite(value):
            raise ValueError('Nonfinite tokenizer float requires special handling')
        return repr(value)
    if kind == 4:return json.dumps(value, ensure_ascii=False)
    if kind == 21:return '&'+json.dumps(value, ensure_ascii=False)
    raise ValueError('Unsupported literal type %s'%kind)


def recover(data:bytes)->str:
    parsed=gdsc_tools.parse(data)
    layout=dict(parsed['layout'])
    lines=[]
    row=''
    row_num=0
    for index,token in enumerate(parsed['tokens']):
        new_row=index==0 or index in layout
        if new_row:
            if row_num:
                lines.append(row.rstrip())
            target=parsed['raw_tokens'][index][2]
            while len(lines)<target-1:
                lines.append('')
            row_num=len(lines)+1
            row=' '*(layout.get(index,1)-1)
        else:
            row+=' '
        kind=token[0]
        if kind in (1,2):
            row+=token[1]
        elif kind==3:
            row+=literal_text(token[1])
        elif kind in SPELL:
            row+=SPELL[kind]
        else:
            raise ValueError('Unsupported token %s'%TOKEN_NAMES[kind])
    if row_num:lines.append(row.rstrip())
    return '\n'.join(lines)+'\n'


def lex(text:str):
    """Independent source lexer for checking recovered literals and tokens.

    It is deliberately not a Godot syntax/semantic parser.
    """
    i=0; line=1; column=1; tokens=[]; layout=[]; last_line=1
    continuation=False
    while i<len(text):
        ch=text[i]
        if ch in ' \t\r':
            column += 4-(column-1)%4 if ch=='\t' else 1
            i+=1;continue
        if ch=='\n':
            line+=1;column=1;i+=1;continue
        if ch=='#':
            end=text.find('\n',i)
            i=len(text) if end<0 else end;continue
        if text.startswith('\\\n',i):
            i+=2;line+=1;column=1;continuation=True;continue
        start=i;start_line=line;start_col=column
        stringname=ch=='&' and i+1<len(text) and text[i+1] in "\"'"
        if stringname or ch in "\"'":
            if stringname:i+=1
            q=text[i]; delimiter=q*3 if text.startswith(q*3,i) else q
            j=i+len(delimiter)
            while j<len(text):
                if text[j]=='\\':j+=2;continue
                if text.startswith(delimiter,j):break
                j+=1
            if j>=len(text):raise ValueError('Unterminated string at line %s'%line)
            raw=text[i:j+len(delimiter)]
            value=ast.literal_eval(raw)
            token=(3,(21 if stringname else 4,value))
            i=j+len(delimiter)
        elif ch=='@':
            match=IDENT.match(text,i+1)
            if match is None:raise ValueError('Invalid annotation')
            i=match.end();token=(1,text[start:i])
        elif ch.isdigit() or ch=='.' and i+1<len(text) and text[i+1].isdigit():
            match=NUMBER.match(text,i)
            if not match:raise ValueError('Invalid number')
            i=match.end();word=match.group(0).replace('_','')
            if word.lower().startswith(('0x','0b')):
                token=(3,(2,int(word,0)))
            elif '.' in word or 'e' in word.lower():
                token=(3,(3,float(word).hex()))
            else:token=(3,(2,int(word)))
        elif ch.isalpha() or ch=='_' or ord(ch)>127:
            match=IDENT.match(text,i)
            if match is None:raise ValueError('Invalid identifier')
            i=match.end();word=match.group(0)
            if word=='null':token=(3,(0,None))
            elif word in ('true','false'):token=(3,(1,int(word=='true')))
            else:token=KEYWORDS.get(word,(2,word))
        else:
            for spelling,kind in OPS:
                if text.startswith(spelling,i):
                    i+=len(spelling);token=(kind,);break
            else:raise ValueError('Unknown character %r at line %s'%(ch,line))
        if tokens and start_line>last_line and not continuation:
            layout.append((len(tokens),start_col))
        continuation=False
        segment=text[start:i]
        if '\n' in segment:
            line+=segment.count('\n');column=len(segment.rsplit('\n',1)[1])+1
        else:column+=len(segment)
        last_line=line
        # The engine tokenizer stores a leading minus with numeric constants.
        # Merge only when an operand is expected, matching the buffer format.
        if token[0]==3 and token[1][0] in (2,3) and tokens and tokens[-1]==(23,):
            prev=tokens[-2] if len(tokens)>1 else None
            operand_before = prev is not None and (prev[0] in (2,3,65,74,76,78,91,92,93,94))
            if not operand_before:
                kind,value=token[1]
                token=(3,(kind,-value if kind==2 else (-float.fromhex(value)).hex()))
                tokens.pop()
                # No physical boundary is lost: generated negative numbers are adjacent.
        tokens.append(token)
    return {'tokens':tokens,'layout':layout}


def verify_text(source,data):
    expected=gdsc_tools.parse(data)
    actual=lex(source)
    return {'tokens_equal':expected['tokens']==actual['tokens'],
            'layout_equal':expected['layout']==actual['layout'],
            'expected_tokens':len(expected['tokens']),'source_tokens':len(actual['tokens']),
            'differences':gdsc_tools.differences(expected['tokens'],actual['tokens'],3),
            'layout_differences':gdsc_tools.differences(expected['layout'],actual['layout'],3)}

if __name__ == '__main__':
    import argparse
    import zipfile
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('aab', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Output already exists: use a new directory.')
    args.output.mkdir(parents=True)
    report = {}
    with zipfile.ZipFile(args.aab) as archive:
        for name in archive.namelist():
            if not name.startswith('assetPackInstallTime/assets/') or not name.endswith('.gdc'):
                continue
            relative = Path(name).relative_to('assetPackInstallTime/assets').with_suffix('.gd')
            if '..' in relative.parts:
                raise ValueError('Unsafe archive path')
            data = archive.read(name)
            text = recover(data)
            validation = verify_text(text, data)
            if not (validation['tokens_equal'] and validation['layout_equal']):
                raise ValueError('Token/layout mismatch: ' + str(relative))
            destination = args.output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text, encoding='utf8')
            report[str(relative)] = validation
    (args.output / 'LEXICAL_REPORT.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print('Recovered and lexically checked scripts:', len(report))

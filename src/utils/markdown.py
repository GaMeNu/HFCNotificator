class md:
    h1_ = '#'
    h2_ = '##'
    h3_ = '###'
    q_ = '>'
    bq_ = '>>>'

    b_ = '**'
    i_ = '_'
    u_ = '__'
    s_ = '~~'
    c_ = '`'
    bc_ = '```'

    @staticmethod
    def h1(text: str):
        return f'{md.h1_} {text}'

    @staticmethod
    def h2(text: str):
        return f'{md.h2_} {text}'

    @staticmethod
    def h3(text: str):
        return f'{md.h3_} {text}'

    @staticmethod
    def q(text: str):
        return f'{md.q_} {text}'

    @staticmethod
    def bq(text: str):
        return f'{md.bq_} {text}'

    @staticmethod
    def b(text: str):
        return f'{md.b_}{text}{md.b_}'

    @staticmethod
    def i(text: str):
        return f'{md.i_}{text}{md.i_}'

    @staticmethod
    def u(text: str):
        return f'{md.u_}{text}{md.u_}'

    @staticmethod
    def s(text: str):
        return f'{md.s_}{text}{md.s_}'

    @staticmethod
    def c(text: str):
        return f'{md.c_}{text}{md.c_}'

    @staticmethod
    def bc(text: str, lang: str = ''):
        return f'{md.bc_}{lang}\n{text}\n{md.bc_}'

    @staticmethod
    def hl(label: str, link: str):
        return f'[{label}]({link})'
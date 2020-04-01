from typing import Optional, Union

import attr
import pycparser.c_ast as ca

from .c_types import (
    Type as CType,
    TypeMap,
    primitive_size,
    resolve_typedefs,
    type_to_string,
)


@attr.s(cmp=False, repr=False)
class Type:
    """
    Type information for an expression, which may improve over time. The least
    specific type is any (initially the case for e.g. arguments); this might
    get refined into intish if the value gets used for e.g. an integer add
    operation, or into u32 if it participates in a logical right shift.
    Types cannot change except for improvements of this kind -- thus concrete
    types like u32 can never change into anything else, and e.g. ints can't
    become floats.
    """

    K_INT = 1
    K_PTR = 2
    K_FLOAT = 4
    K_INTPTR = 3
    K_ANY = 7
    SIGNED = 1
    UNSIGNED = 2
    ANY_SIGN = 3

    kind: int = attr.ib()
    size: Optional[int] = attr.ib()
    sign: int = attr.ib()
    uf_parent: Optional["Type"] = attr.ib(default=None)
    ptr_to: Optional[Union["Type", CType]] = attr.ib(default=None)

    def unify(self, other: "Type") -> bool:
        """
        Try to set this type equal to another. Returns true on success.
        Once set equal, the types will always be equal (we use a union-find
        structure to ensure this).
        """
        x = self.get_representative()
        y = other.get_representative()
        if x is y:
            return True
        if x.size is not None and y.size is not None and x.size != y.size:
            return False
        if x.ptr_to is not None and y.ptr_to is not None and x.ptr_to != y.ptr_to:
            return False
        size = x.size if x.size is not None else y.size
        ptr_to = x.ptr_to if x.ptr_to is not None else y.ptr_to
        kind = x.kind & y.kind
        sign = x.sign & y.sign
        if size in [8, 16]:
            kind &= ~Type.K_FLOAT
        if size in [8, 16, 64]:
            kind &= ~Type.K_PTR
        if kind == 0 or sign == 0:
            return False
        if kind == Type.K_PTR:
            size = 32
        if sign != Type.ANY_SIGN:
            assert kind == Type.K_INT
        x.kind = kind
        x.size = size
        x.sign = sign
        x.ptr_to = ptr_to
        y.uf_parent = x
        return True

    def get_representative(self) -> "Type":
        if self.uf_parent is None:
            return self
        self.uf_parent = self.uf_parent.get_representative()
        return self.uf_parent

    def is_float(self) -> bool:
        return self.get_representative().kind == Type.K_FLOAT

    def is_pointer(self) -> bool:
        return self.get_representative().kind == Type.K_PTR

    def is_unsigned(self) -> bool:
        return self.get_representative().sign == Type.UNSIGNED

    def get_size(self) -> int:
        return self.get_representative().size or 32

    def to_decl(self) -> str:
        ret = str(self)
        return ret if ret.endswith("*") else ret + " "

    def __str__(self) -> str:
        type = self.get_representative()
        size = type.size or 32
        sign = "s" if type.sign & Type.SIGNED else "u"
        if type.kind == Type.K_ANY:
            if type.size is not None:
                return f"?{size}"
            return "?"
        if type.kind == Type.K_PTR:
            if type.ptr_to is not None:
                if isinstance(type.ptr_to, Type):
                    return (str(type.ptr_to) + " *").replace("* *", "**")
                return type_to_string(ca.PtrDecl([], type.ptr_to))
            return "void *"
        if type.kind == Type.K_FLOAT:
            return f"f{size}"
        return f"{sign}{size}"

    def __repr__(self) -> str:
        type = self.get_representative()
        signstr = ("+" if type.sign & Type.SIGNED else "") + (
            "-" if type.sign & Type.UNSIGNED else ""
        )
        kindstr = (
            ("I" if type.kind & Type.K_INT else "")
            + ("P" if type.kind & Type.K_PTR else "")
            + ("F" if type.kind & Type.K_FLOAT else "")
        )
        sizestr = str(type.size) if type.size is not None else "?"
        return f"Type({signstr + kindstr + sizestr})"

    @staticmethod
    def any() -> "Type":
        return Type(kind=Type.K_ANY, size=None, sign=Type.ANY_SIGN)

    @staticmethod
    def intish() -> "Type":
        return Type(kind=Type.K_INT, size=None, sign=Type.ANY_SIGN)

    @staticmethod
    def intptr() -> "Type":
        return Type(kind=Type.K_INTPTR, size=None, sign=Type.ANY_SIGN)

    @staticmethod
    def ptr(type: Optional[Union["Type", CType]] = None) -> "Type":
        return Type(kind=Type.K_PTR, size=32, sign=Type.ANY_SIGN, ptr_to=type)

    @staticmethod
    def f32() -> "Type":
        return Type(kind=Type.K_FLOAT, size=32, sign=Type.ANY_SIGN)

    @staticmethod
    def f64() -> "Type":
        return Type(kind=Type.K_FLOAT, size=64, sign=Type.ANY_SIGN)

    @staticmethod
    def s8() -> "Type":
        return Type(kind=Type.K_INT, size=8, sign=Type.SIGNED)

    @staticmethod
    def u8() -> "Type":
        return Type(kind=Type.K_INT, size=8, sign=Type.UNSIGNED)

    @staticmethod
    def s16() -> "Type":
        return Type(kind=Type.K_INT, size=16, sign=Type.SIGNED)

    @staticmethod
    def u16() -> "Type":
        return Type(kind=Type.K_INT, size=16, sign=Type.UNSIGNED)

    @staticmethod
    def s32() -> "Type":
        return Type(kind=Type.K_INT, size=32, sign=Type.SIGNED)

    @staticmethod
    def u32() -> "Type":
        return Type(kind=Type.K_INT, size=32, sign=Type.UNSIGNED)

    @staticmethod
    def u64() -> "Type":
        return Type(kind=Type.K_INT, size=64, sign=Type.UNSIGNED)

    @staticmethod
    def of_size(size: int) -> "Type":
        return Type(kind=Type.K_ANY, size=size, sign=Type.ANY_SIGN)

    @staticmethod
    def bool() -> "Type":
        return Type.intish()


def type_from_ctype(ctype: CType, typemap: TypeMap) -> Type:
    ctype = resolve_typedefs(ctype, typemap)
    if isinstance(ctype, (ca.PtrDecl, ca.ArrayDecl)):
        return Type.ptr(ctype.type)
    if isinstance(ctype, ca.FuncDecl):
        return Type.ptr(ctype)
    if isinstance(ctype, ca.TypeDecl):
        if isinstance(ctype.type, (ca.Struct, ca.Union)):
            return Type.any()
        names = ["int"] if isinstance(ctype.type, ca.Enum) else ctype.type.names
        if "double" in names:
            return Type.f64()
        if "float" in names:
            return Type.f32()
        size = 8 * primitive_size(ctype.type)
        sign = Type.UNSIGNED if "unsigned" in names else Type.SIGNED
        return Type(kind=Type.K_INT, size=size, sign=sign)


def get_field_name(type: Type, offset: int, typemap: TypeMap) -> Optional[str]:
    type = type.get_representative()
    if not type.ptr_to or isinstance(type.ptr_to, Type):
        return None
    ctype = type.ptr_to
    ctype = resolve_typedefs(ctype, typemap)
    if (
        isinstance(ctype, ca.TypeDecl)
        and isinstance(ctype.type, (ca.Struct, ca.Union))
        and ctype.type.name
    ):
        struct = typemap.struct_defs.get(ctype.type.name)
        if struct:
            fields = struct.fields.get(offset)
            if fields:
                # TODO: in case of unions, pick the field name that best corresponds
                # to the extracted type
                return fields[-1].name
    return None

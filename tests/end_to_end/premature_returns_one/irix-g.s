.set noat      # allow manual use of $at
.set noreorder # don't insert nops after branches


glabel test
/* 000090 00400090 10800003 */  beqz  $a0, .L004000A0
/* 000094 00400094 00000000 */   nop
/* 000098 00400098 03E00008 */  jr    $ra
/* 00009C 0040009C 24020001 */   addiu $v0, $zero, 1

.L004000A0:
/* 0000A0 004000A0 03E00008 */  jr    $ra
/* 0000A4 004000A4 00001025 */   move  $v0, $zero

/* 0000A8 004000A8 03E00008 */  jr    $ra
/* 0000AC 004000AC 00000000 */   nop

/* 0000B0 004000B0 03E00008 */  jr    $ra
/* 0000B4 004000B4 00000000 */   nop

/* 0000B8 004000B8 00000000 */  nop
/* 0000BC 004000BC 00000000 */  nop

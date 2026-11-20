.text
gate:
    // First direct pull-up only. Nested resume and reconnects use stock reset.
    ldr x9, [x29, #8]
    adr x10, gate
    movz x11, #(CALLER_DELTA & 0xffff)
    movk x11, #(CALLER_DELTA >> 16), lsl #16
    add x10, x10, x11
    cmp x9, x10
    b.ne original
    adr x9, gate
    movz x10, #(FLAG_DELTA & 0xffff)
    movk x10, #(FLAG_DELTA >> 16), lsl #16
    add x9, x9, x10
    mov w10, #1
claim:
    ldaxr w11, [x9]
    cbnz w11, already_claimed
    stlxr w12, w10, [x9]
    cbnz w12, claim
    mov w0, wzr
    ret
already_claimed:
    clrex
original:
    .inst ORIGINAL_RESET
.org 96
run_stop_return:
    // A failed reset can also branch to this epilogue. Check the call site.
    cbz w0, resume
    adr x9, gate
    movz x10, #(RUN_RETURN_DELTA & 0xffff)
    movk x10, #(RUN_RETURN_DELTA >> 16), lsl #16
    add x9, x9, x10
    cmp x30, x9
    b.ne resume
    mov x5, #1
    b start_delay
resume:
    ldp x20, x19, [sp, #0x20]
    .inst RUN_RESUME
start_delay:
    mrs x4, cntfrq_el0
    cbz x4, park
    mul x4, x4, x5
    isb
    mrs x5, cntpct_el0
wait:
    isb
    mrs x6, cntpct_el0
    sub x6, x6, x5
    cmp x6, x4
    b.lo wait
    movz w0, #8
    movk w0, #0x8400, lsl #16
    mov x1, xzr
    mov x2, xzr
    mov x3, xzr
    smc #0
park:
    wfe
    b park

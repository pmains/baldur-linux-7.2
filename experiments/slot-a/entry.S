// Terminal probe at primary_entry, before any access to the DTB in x0.

.text
entry_probe:
    mrs x4, cntfrq_el0
    cbz x4, park
    mov x5, #DELAY_SECONDS
    mul x4, x4, x5
    isb
    mrs x5, cntpct_el0
wait_for_delay:
    isb
    mrs x6, cntpct_el0
    sub x6, x6, x5
    cmp x6, x4
    b.lo wait_for_delay

    // Both variants request the same PSCI SYSTEM_OFF marker.
    movz w0, #8
    movk w0, #0x8400, lsl #16
    mov x1, xzr
    mov x2, xzr
    mov x3, xzr
    smc #0
park:
    wfe
    b park

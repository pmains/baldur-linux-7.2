# Combined Linux 7.2 pilot on Baldur

Baldur is the unlocked CPH2583 OnePlus 12. These experiments used local combined images after Developer Preview 01. The release tag and its verification matrix remain the reference for that preview.

## Verified on the combined RAM image

The pilot reached its own PID 1, displayed the tty1 banner and boot ID, brought up authenticated USB SSH and ACM, and mounted the prepared ext4 root read-only with journal replay disabled. The combined software path exercised Adreno with Turnip and the Hexagon NPU through FastRPC. Internal UFS, battery status, CPU thermal policies, and the board thermistors were also exercised. Production charging behavior, sustained inference qualification, and suspend/resume remain open.

In a cooler-attached mixed Qwen 9B test, MIN_SVS completed 48.0 tokens/min, LOW_SVS 24.0, and SVS 7.2 under the same existing thermal guards. The throughput includes cooldown and counts completed requests. The three five-minute phases started at progressively warmer NPU temperatures. The hardware clock frequency was unverified. See [measurements](../experiments/hmx/results.jsonl) and the [HMX vote patch](../experiments/hmx/hmx-v75.patch).

## Slot A results

- The early FDT merge replays with the slot A vendor bases and overlays. The added bounded symbol-name check allowed all 24 compatible overlays through merge and retirement with their metadata intact. The 24 alternate-board cases still failed the compatibility check. Duplicate names and property-count limits remained enforced.
- A-selected Fastboot accepted the full upload size and the same declared kernel length using an entry-only VT3 control. Zeroing its Android boot-header OS version reproduced the transport disconnect. Setting that field to 469762467 in the unchanged 7.2 payload let it reach PID 1 and verified USB SSH with A selected.
- The corresponding installed slot A pilot showed no usable USB endpoint and exhausted A's retries. The exact failure stage is unverified. The installed loader's return to VT3 does not establish that it entered Linux on A.
- The matched one- and five-second kernel-entry pair differed by 4.12 seconds in B-selected RAM trials and 0.12 seconds on the earlier installed A pilot. The two installed timings do not establish whether Linux reached the marker. The bootloader log exposed only B.
- The fallback was recovered with D7b. The read-only ext4 check and clean journal state allowed restoration of the exact VT3 startup image. Normal VT3 6.1 on B was subsequently verified over authenticated USB SSH.

## Source and local artifacts

[Slot A experiment source](../experiments/slot-a/) records the early symbol patch, the entry-only timing marker, the captured pilot source inputs, and the exact header adjustment. Apply the symbol patch after the early FDT patch when reviewing the merge. The pilot source snapshot is separate from the tagged Preview 01 build. It relies on local firmware, the prepared root, and additional local build inputs.

The original pilot RAM wrapper SHA-256 is `dea30b6c142d889e23496c565210517ba25a98b54d41bfeff6557b3832312285`. The header-only script requires that input hash and reproduces the A-context RAM image. The unsigned installed candidate SHA-256 was `aec6c369a99d9cb6230999e6ffa683733c4166adaf391ea7b312ad56c9ab74fe`. It remains a failed installed pilot, with no qualified persistent boot or independent cold start. Keep VT3 B available as the recovery system.

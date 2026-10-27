"""
CAM++ Speaker Verification & Comparison Tool (CLI & Programmatic)
Alibaba DAMO / ModelScope CAM++ (Conformer Architecture)

Usage:
    python verify_speakers_campplus.py <audio1> <audio2> [--threshold 0.60]

Example:
    python verify_speakers_campplus.py voice_a.wav voice_b.wav
"""

import sys
import os
import argparse

# Force UTF-8 for console output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.srt_service.speaker_verification import SpeakerVerificationService


def main():
    parser = argparse.ArgumentParser(description="CAM++ Audio Speaker Verification & Comparison Tool")
    parser.add_argument("audio1", nargs="?", help="Path to first audio file (wav/mp3/m4a/etc.)")
    parser.add_argument("audio2", nargs="?", help="Path to second audio file")
    parser.add_argument("--threshold", type=float, default=0.60, help="Similarity threshold (default: 0.60)")
    parser.add_argument("--demo", action="store_true", help="Run with built-in CAM++ demo speakers")

    args = parser.parse_args()

    cache_examples = os.path.expanduser(r"~/.cache/modelscope/hub/models/iic/speech_campplus_sv_zh-cn_16k-common/examples")

    if args.demo or (not args.audio1 and not args.audio2):
        if os.path.exists(cache_examples):
            spk1_a = os.path.join(cache_examples, "speaker1_a_cn_16k.wav")
            spk1_b = os.path.join(cache_examples, "speaker1_b_cn_16k.wav")
            spk2_a = os.path.join(cache_examples, "speaker2_a_cn_16k.wav")

            print("=" * 65)
            print("🎙️ CAM++ SPEAKER VERIFICATION DEMO (Alibaba DAMO)")
            print("=" * 65)

            print("\n🔍 Test 1: Speaker 1 (Sample A) vs Speaker 1 (Sample B) [SAME PERSON]")
            res1 = SpeakerVerificationService.compare_speakers(spk1_a, spk1_b, threshold=args.threshold)
            print(f"   Similarity Score: {res1['similarity']} ({res1['similarity_pct']})")
            print(f"   Verdict:          {res1['verdict']}")
            print(f"   Confidence:       {res1['confidence']}")
            print(f"   Result:           {'✅ MATCH (មនុស្សតែមួយ)' if res1['is_same_speaker'] else '❌ NO MATCH'}")

            print("\n🔍 Test 2: Speaker 1 (Sample A) vs Speaker 2 (Sample A) [DIFFERENT PERSONS]")
            res2 = SpeakerVerificationService.compare_speakers(spk1_a, spk2_a, threshold=args.threshold)
            print(f"   Similarity Score: {res2['similarity']} ({res2['similarity_pct']})")
            print(f"   Verdict:          {res2['verdict']}")
            print(f"   Confidence:       {res2['confidence']}")
            print(f"   Result:           {'✅ MATCH' if res2['is_same_speaker'] else '❌ DIFFERENT (មនុស្សខុសគ្នា)'}")
            print("=" * 65)
            return
        else:
            parser.print_help()
            return

    if not os.path.exists(args.audio1):
        print(f"❌ Error: File not found: {args.audio1}")
        sys.exit(1)
    if not os.path.exists(args.audio2):
        print(f"❌ Error: File not found: {args.audio2}")
        sys.exit(1)

    print("=" * 65)
    print("🎙️ CAM++ AUDIO SPEAKER COMPARISON (ការប្រៀបធៀបសំឡេងមនុស្ស)")
    print("=" * 65)
    print(f"🔊 Audio 1: {args.audio1}")
    print(f"🔊 Audio 2: {args.audio2}")
    print(f"⚙️ Threshold: {args.threshold}")
    print("\n⏳ Extracting 192-dim voice embeddings with CAM++...")

    res = SpeakerVerificationService.compare_speakers(args.audio1, args.audio2, threshold=args.threshold)

    print("\n📊 លទ្ធផលនៃការវិភាគ (ANALYSIS RESULTS):")
    print("-" * 65)
    print(f"• ពិន្ទុភាពដូចគ្នា (Similarity):  {res['similarity']} ({res['similarity_pct']})")
    print(f"• សេចក្តីសន្និដ្ឋាន (Verdict):    {res['verdict']}")
    print(f"• កម្រិតជឿជាក់ (Confidence):   {res['confidence']}")
    print("-" * 65)
    if res["is_same_speaker"]:
        print("✅ សំឡេងទាំងពីរជា មនុស្សតែមួយ (Same Person)! Voice profiles match successfully.")
    else:
        print("❌ សំឡេងទាំងពីរជា មនុស្សខុសគ្នា (Different Persons). Voices belong to separate speakers.")
    print("=" * 65)


if __name__ == "__main__":
    main()

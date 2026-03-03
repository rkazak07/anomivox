#!/usr/bin/env python3
# rgw_bucket_manager.py
#
# Lists objects in a Ceph RGW (S3-compatible) bucket
# Optionally deletes them with safety checks

import os
import sys
import argparse
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# ------------------------
# Helpers
# ------------------------

def human_size(n):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.2f}{unit}"
        n /= 1024
    return f"{n:.2f}PB"


def get_s3_client():
    endpoint = os.getenv("S3_ENDPOINT", "http://192.168.25.169:8080").strip()
    access_key = os.getenv("S3_ACCESS_KEY", "6OY3V3KQQDDWOOWVESZA").strip()
    secret_key = os.getenv("S3_SECRET_KEY", "GYa2yYd0nGAEWDRpKwOipFa0XbhTaQpbMG7HmLq5").strip()
    region = os.getenv("S3_REGION", "us-east-1")
    verify_tls = os.getenv("S3_VERIFY_TLS", "true").lower() in ("1", "true", "yes")

    if not endpoint or not access_key or not secret_key:
        print("❌ S3 bağlantı bilgileri eksik!", file=sys.stderr)
        print("Gerekli ENV değişkenleri:", file=sys.stderr)
        print("  S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY", file=sys.stderr)
        sys.exit(2)

    cfg = Config(
        region_name=region,
        retries={"max_attempts": 5, "mode": "standard"},
        s3={"addressing_style": "path"},
        connect_timeout=10,
        read_timeout=120,
    )

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        verify=verify_tls,
        config=cfg,
    )


# ------------------------
# Main logic
# ------------------------

def list_objects(s3, bucket, prefix=None):
    paginator = s3.get_paginator("list_objects_v2")
    kwargs = {"Bucket": bucket}
    if prefix:
        kwargs["Prefix"] = prefix

    total_size = 0
    total_count = 0
    objects = []

    for page in paginator.paginate(**kwargs):
        for obj in page.get("Contents", []):
            objects.append(obj)
            total_size += obj["Size"]
            total_count += 1

    return objects, total_count, total_size


def delete_objects(s3, bucket, objects, dry_run=False):
    deleted = 0

    for obj in objects:
        key = obj["Key"]
        if dry_run:
            print(f"[DRY-RUN] Silinecek: {key}")
        else:
            s3.delete_object(Bucket=bucket, Key=key)
            print(f"🗑️ Silindi: {key}")
            deleted += 1

    return deleted


# ------------------------
# CLI
# ------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Ceph RGW S3 bucket listeleme & silme aracı"
    )
    parser.add_argument("--bucket", required=True, help="Bucket adı")
    parser.add_argument("--prefix", help="Prefix filtre (opsiyonel)")
    parser.add_argument("--delete", action="store_true", help="Objeleri sil")
    parser.add_argument("--dry-run", action="store_true", help="Silmeden önce göster")
    parser.add_argument("--yes", action="store_true", help="Onay sormadan sil")

    args = parser.parse_args()

    s3 = get_s3_client()

    try:
        objects, count, size = list_objects(s3, args.bucket, args.prefix)
    except ClientError as e:
        print(f"❌ Bucket erişim hatası: {e}", file=sys.stderr)
        sys.exit(1)

    if count == 0:
        print("📭 Bucket boş.")
        return

    print("\n📦 BULUNAN OBJELER")
    print("-" * 60)
    for obj in objects:
        print(f"{obj['Key']:<50} {human_size(obj['Size'])}")

    print("-" * 60)
    print(f"Toplam obje  : {count}")
    print(f"Toplam boyut : {human_size(size)}")

    if args.delete:
        if not args.yes:
            print("\n⚠️ DİKKAT: Bu işlem geri alınamaz!")
            confirm = input("Silme işlemine devam edilsin mi? (yes/no): ").strip().lower()
            if confirm != "yes":
                print("❎ Silme iptal edildi.")
                return

        deleted = delete_objects(
            s3,
            args.bucket,
            objects,
            dry_run=args.dry_run
        )

        if args.dry_run:
            print("\n✅ Dry-run tamamlandı. Gerçek silme yapılmadı.")
        else:
            print(f"\n✅ Toplam silinen obje: {deleted}")


if __name__ == "__main__":
    main()

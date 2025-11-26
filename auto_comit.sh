#!/bin/bash

# Tambahkan semua perubahan
git add -A

# Ambil daftar file yang berubah beserta statusnya
changes=$(git diff --cached --name-status)

# Jika tidak ada perubahan, keluar
if [ -z "$changes" ]; then
    echo "✅ Tidak ada perubahan untuk di-commit."
    exit 0
fi

# Buat pesan commit otomatis
commit_msg="🔄 Auto Commit:
"

while IFS= read -r line; do
    commit_msg+=" - $line"$'\n'
done <<< "$changes"

# Commit
git commit -m "$commit_msg"

# Deteksi nama branch aktif
branch=$(git symbolic-ref --short HEAD)

# Push ke remote (origin)
git push origin "$branch"

echo "✅ Commit dan push berhasil ke branch '$branch'"
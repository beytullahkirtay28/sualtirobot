#!/bin/bash
#
# ROV symlink kurulumu (Senaryo A)
# Bu scripti git klasörünün içinden çalıştır:
#   cd ~/Desktop/git
#   bash scripts/rov-symlink-kur.sh
#
# Yaptığı: ~/Desktop/ROV silinir, ~/Desktop/git'e sembolik link yapılır.
# Sonra her git pull → ROV otomatik güncel.

set -e

GIT_DIR="$HOME/Desktop/git"
ROV_DIR="$HOME/Desktop/ROV"
BACKUP_DIR="$HOME/rov-yedek-$(date +%Y%m%d-%H%M%S)"

echo "============================================================"
echo "  ROV → GIT SYMLINK KURULUMU"
echo "============================================================"
echo ""

# --- 1. Çalıştırılan klasör doğru mu? ---
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." &> /dev/null && pwd )"
if [ "$SCRIPT_DIR" != "$GIT_DIR" ]; then
    echo "⚠️  Beklenen yol: $GIT_DIR"
    echo "   Şu anda buradan çalışıyor: $SCRIPT_DIR"
    echo ""
    read -p "Yine de devam edilsin mi? [e/H]: " yanit
    if [ "$yanit" != "e" ] && [ "$yanit" != "E" ]; then
        echo "İptal."
        exit 1
    fi
    GIT_DIR="$SCRIPT_DIR"
fi

# --- 2. Git klasörü gerçekten git repo mu? ---
if [ ! -d "$GIT_DIR/.git" ]; then
    echo "❌ $GIT_DIR bir git repository değil (.git klasörü yok)"
    exit 1
fi
echo "✅ Git repo: $GIT_DIR"

# --- 3. ROV zaten symlink mi? ---
if [ -L "$ROV_DIR" ]; then
    HEDEF=$(readlink -f "$ROV_DIR")
    if [ "$HEDEF" = "$GIT_DIR" ]; then
        echo "✅ ROV zaten doğru symlink: $ROV_DIR -> $GIT_DIR"
        echo "   Yapılacak bir şey yok."
        exit 0
    else
        echo "⚠️  ROV başka bir yere symlink: $ROV_DIR -> $HEDEF"
        read -p "Düzeltilsin mi? [E/h]: " yanit
        if [ "$yanit" = "h" ] || [ "$yanit" = "H" ]; then
            echo "İptal."; exit 1
        fi
        rm "$ROV_DIR"
    fi
fi

# --- 4. ROV klasörü var mı? Yedekle. ---
if [ -d "$ROV_DIR" ]; then
    echo ""
    echo "▶ Mevcut ROV klasöründe git'te OLMAYAN dosyalar var mı kontrol ediliyor..."

    UNIQUE_FILES=$(diff -rq "$GIT_DIR" "$ROV_DIR" 2>/dev/null | grep "Only in $ROV_DIR" || true)

    if [ -n "$UNIQUE_FILES" ]; then
        echo ""
        echo "⚠️  ROV'da git'te olmayan dosyalar bulundu:"
        echo "$UNIQUE_FILES" | sed 's/^/   /'
        echo ""
        echo "   Bunlar şuraya yedeklenecek: $BACKUP_DIR"
        read -p "Devam? [E/h]: " yanit
        if [ "$yanit" = "h" ] || [ "$yanit" = "H" ]; then
            echo "İptal."; exit 1
        fi
        mkdir -p "$BACKUP_DIR"
        cp -r "$ROV_DIR/." "$BACKUP_DIR/"
        echo "✅ Yedek alındı: $BACKUP_DIR"
    else
        echo "✅ ROV ile git aynı, yedek gerekmiyor."
    fi

    echo ""
    echo "▶ ROV klasörü siliniyor: $ROV_DIR"
    rm -rf "$ROV_DIR"
fi

# --- 5. Symlink oluştur ---
echo ""
echo "▶ Symlink oluşturuluyor: $ROV_DIR -> $GIT_DIR"
ln -s "$GIT_DIR" "$ROV_DIR"

# --- 6. Doğrula ---
echo ""
echo "▶ Doğrulama:"
ls -la "$HOME/Desktop/ROV" | head -1
echo ""
echo "ROV içeriği:"
ls "$ROV_DIR/" | sed 's/^/  /'

echo ""
echo "============================================================"
echo "  ✅ SYMLINK KURULDU"
echo "============================================================"
echo ""
echo "Bundan sonra güncelleme için:"
echo "  cd $GIT_DIR && git pull"
echo "  # ROV otomatik güncel olur"
echo ""
echo "Servisleri kurmak/güncellemek için:"
echo "  bash $ROV_DIR/scripts/rov-install.sh"
echo ""
if [ -d "$BACKUP_DIR" ]; then
    echo "Yedek dosyalar burada (gerekmiyorsa silebilirsin):"
    echo "  $BACKUP_DIR"
    echo ""
fi

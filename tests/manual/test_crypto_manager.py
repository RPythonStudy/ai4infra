#!/usr/bin/env python3

import os
import unittest
import shutil
import tempfile
from pathlib import Path

# Add project root to sys.path to import modules
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, "scripts", "ai4infra"))
sys.path.append(os.path.join(PROJECT_ROOT, "src")) # Add src for common module

from utils.container.crypto_manager import encrypt_file, decrypt_file

class TestCryptoManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.input_file = os.path.join(self.test_dir, "test_input.txt")
        self.enc_file = os.path.join(self.test_dir, "test_output.gpg")
        self.dec_file = os.path.join(self.test_dir, "test_restored.txt")
        self.passphrase = "mysecretpassword123"

        # Create dummy input file
        with open(self.input_file, "w") as f:
            f.write("This is a secret message that should be encrypted.")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_encryption_decryption(self):
        # 1. Encrypt
        print(f"\n[Test] Encrypting {self.input_file} to {self.enc_file}...")
        success = encrypt_file(self.input_file, self.enc_file, self.passphrase)
        self.assertTrue(success, "Encryption failed")
        self.assertTrue(os.path.exists(self.enc_file), "Encrypted file not created")
        
        # Verify file content is NOT plain text
        with open(self.enc_file, "rb") as f:
            content = f.read()
            self.assertNotIn(b"This is a secret message", content, "Content was not encrypted!")

        # 2. Decrypt
        print(f"[Test] Decrypting {self.enc_file} to {self.dec_file}...")
        success = decrypt_file(self.enc_file, self.dec_file, self.passphrase)
        self.assertTrue(success, "Decryption failed")
        self.assertTrue(os.path.exists(self.dec_file), "Decrypted file not created")

        # 3. Compare content
        with open(self.input_file, "r") as f1, open(self.dec_file, "r") as f2:
            original = f1.read()
            restored = f2.read()
            self.assertEqual(original, restored, "Restored content does not match original") 
            print("[Test] Content match verified!")

    def test_wrong_password(self):
        # Encrypt first
        encrypt_file(self.input_file, self.enc_file, self.passphrase)
        
        # Try to decrypt with wrong password
        print(f"[Test] Attempting decryption with WRONG password...")
        success = decrypt_file(self.enc_file, self.dec_file, "wrongpassword")
        self.assertFalse(success, "Decryption should fail with wrong password")

if __name__ == "__main__":
    unittest.main()

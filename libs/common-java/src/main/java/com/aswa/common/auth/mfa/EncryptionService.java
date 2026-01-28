package com.aswa.common.auth.mfa;

/**
 * Encryption service interface for encrypting MFA secrets.
 */
public interface EncryptionService {

    /**
     * Encrypt a value.
     *
     * @param plaintext the value to encrypt
     * @return encrypted value
     */
    String encrypt(String plaintext);

    /**
     * Decrypt a value.
     *
     * @param ciphertext the encrypted value
     * @return decrypted value
     */
    String decrypt(String ciphertext);
}

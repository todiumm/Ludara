package com.ludara.security;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Criptografa o token de sessão com chave mantida no Android Keystore. */
public final class SecurePreferences {
    private static final String KEY_ALIAS = "ludara_session_key_v1";
    private static final String PREFS = "ludara_secure_session";
    private static final String TOKEN = "encrypted_token";
    private static final String IV = "token_iv";
    private static final String ANDROID_KEYSTORE = "AndroidKeyStore";

    private SecurePreferences() {}

    private static SecretKey getOrCreateKey() throws Exception {
        KeyStore store = KeyStore.getInstance(ANDROID_KEYSTORE);
        store.load(null);
        if (store.containsAlias(KEY_ALIAS)) {
            return ((KeyStore.SecretKeyEntry) store.getEntry(KEY_ALIAS, null)).getSecretKey();
        }
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE);
        generator.init(new KeyGenParameterSpec.Builder(KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build());
        return generator.generateKey();
    }

    public static synchronized void saveToken(Context context, String token) throws Exception {
        if (context == null || token == null || token.isEmpty()) throw new IllegalArgumentException("Context/token inválido");
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey());
        byte[] encrypted = cipher.doFinal(token.getBytes(StandardCharsets.UTF_8));
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        boolean ok = prefs.edit()
                .putString(TOKEN, Base64.encodeToString(encrypted, Base64.NO_WRAP))
                .putString(IV, Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP))
                .commit();
        if (!ok) throw new IllegalStateException("Não foi possível salvar a sessão criptografada");
    }

    public static synchronized String loadToken(Context context) throws Exception {
        if (context == null) throw new IllegalArgumentException("Context inválido");
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String encoded = prefs.getString(TOKEN, null);
        String encodedIv = prefs.getString(IV, null);
        if (encoded == null || encodedIv == null) return null;
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(),
                new GCMParameterSpec(128, Base64.decode(encodedIv, Base64.NO_WRAP)));
        byte[] clear = cipher.doFinal(Base64.decode(encoded, Base64.NO_WRAP));
        return new String(clear, StandardCharsets.UTF_8);
    }

    public static synchronized void clearToken(Context context) throws Exception {
        if (context == null) throw new IllegalArgumentException("Context inválido");
        boolean ok = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().clear().commit();
        if (!ok) throw new IllegalStateException("Não foi possível limpar a sessão");
    }
}

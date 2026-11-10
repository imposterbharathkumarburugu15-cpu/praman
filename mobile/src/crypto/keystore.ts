import { generateP256KeyPair, signP256DER, exportPublicKeyToPEM, importPrivateKeyFromDER } from "../../../shared/crypto/p256";
import { canonicalize } from "../../../shared/crypto/canonicalize";

export class AndroidKeystoreBridge {
  private keyPairs: Map<string, { privateKey: CryptoKey; publicKey: CryptoKey; pem: string }> = new Map();

  async generateKey(alias: string = "praman_device_key"): Promise<string> {
    const pair = await generateP256KeyPair();
    const pem = await exportPublicKeyToPEM(pair.publicKey);
    this.keyPairs.set(alias, {
      privateKey: pair.privateKey,
      publicKey: pair.publicKey,
      pem,
    });
    return pem;
  }

  async signEnvelope(alias: string, envelope: Record<string, unknown>): Promise<Uint8Array> {
    const entry = this.keyPairs.get(alias);
    if (!entry) {
      throw new Error(`Key alias ${alias} not found in Keystore`);
    }
    const canonicalBytes = canonicalize(envelope);
    return await signP256DER(entry.privateKey, canonicalBytes);
  }

  getPublicKeyPEM(alias: string): string {
    const entry = this.keyPairs.get(alias);
    if (!entry) {
      throw new Error(`Key alias ${alias} not found in Keystore`);
    }
    return entry.pem;
  }
}

export const keystoreBridge = new AndroidKeystoreBridge();


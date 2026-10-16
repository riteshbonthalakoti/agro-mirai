package expo.modules.smsretriever

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.util.Base64
import androidx.core.content.ContextCompat
import com.google.android.gms.auth.api.phone.SmsRetriever
import com.google.android.gms.common.api.CommonStatusCodes
import com.google.android.gms.common.api.Status
import expo.modules.kotlin.exception.Exceptions
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import expo.modules.kotlin.Promise
import java.security.MessageDigest

/**
 * Android SMS Retriever API (Module 56) -- the farmer's OTP screen never
 * needs the keyboard or a copy-paste: the OS delivers the SMS body to this
 * module directly once it matches the app's signature hash (appended by
 * the backend to every OTP text; see agro_mirai.auth.otp_providers and
 * SMS_APP_HASH). No SMS/phone permission is needed -- that's the whole
 * point of this API over reading the inbox directly.
 */
class SmsRetrieverModule : Module() {
  private var receiver: BroadcastReceiver? = null

  override fun definition() = ModuleDefinition {
    Name("SmsRetriever")

    // Starts listening; resolves with the full SMS body once one arrives
    // that carries this app's hash, or rejects on timeout/error (the JS
    // side has its own fallback: manual entry always still works).
    AsyncFunction("startSmsRetriever") { promise: Promise ->
      val context = appContext.reactContext ?: run {
        promise.reject(Exceptions.ReactContextLost())
        return@AsyncFunction
      }

      stopListening(context)

      val client = SmsRetriever.getClient(context)
      val filter = IntentFilter(SmsRetriever.SMS_RETRIEVED_ACTION)

      client.startSmsRetriever()
        .addOnSuccessListener {
          val newReceiver = object : BroadcastReceiver() {
            override fun onReceive(ctx: Context, intent: Intent) {
              if (intent.action != SmsRetriever.SMS_RETRIEVED_ACTION) return
              val extras = intent.extras ?: return
              val status = extras.get(SmsRetriever.EXTRA_STATUS) as? Status ?: return
              when (status.statusCode) {
                CommonStatusCodes.SUCCESS -> {
                  val message = extras.getString(SmsRetriever.EXTRA_SMS_MESSAGE)
                  stopListening(context)
                  promise.resolve(message)
                }
                CommonStatusCodes.TIMEOUT -> {
                  stopListening(context)
                  promise.reject("ERR_SMS_RETRIEVER_TIMEOUT", "Timed out waiting for the OTP SMS", null)
                }
              }
            }
          }
          receiver = newReceiver
          ContextCompat.registerReceiver(
            context,
            newReceiver,
            filter,
            ContextCompat.RECEIVER_EXPORTED
          )
        }
        .addOnFailureListener { e ->
          promise.reject("ERR_SMS_RETRIEVER_START", "SMS Retriever failed to start: ${e.message}", null)
        }
    }

    AsyncFunction("stopSmsRetriever") {
      appContext.reactContext?.let { stopListening(it) }
    }

    // Dev utility only -- prints the 11-char hash SMS Retriever expects
    // appended to every OTP text (SMS_APP_HASH on the backend). Debug and
    // release currently share the same signing key (android/app/build.gradle),
    // so one hash covers both; re-run this after ever changing the signing config.
    Function("getAppSignatures") {
      val context = appContext.reactContext ?: return@Function emptyList<String>()
      getAppSignatures(context)
    }
  }

  private fun stopListening(context: Context) {
    receiver?.let {
      try {
        context.unregisterReceiver(it)
      } catch (_: IllegalArgumentException) {
        // already unregistered -- fine
      }
    }
    receiver = null
  }

  // Standard Google sample algorithm (AppSignatureHelper): package name +
  // SHA-256 of the signing cert, base64, first 9 bytes -> 11 chars.
  private fun getAppSignatures(context: Context): List<String> {
    val signatures = mutableListOf<String>()
    try {
      val packageName = context.packageName
      val packageManager = context.packageManager
      @Suppress("DEPRECATION")
      val signingInfo = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
        packageManager.getPackageInfo(packageName, PackageManager.GET_SIGNING_CERTIFICATES)
          .signingInfo?.apkContentsSigners
      } else {
        packageManager.getPackageInfo(packageName, PackageManager.GET_SIGNATURES).signatures
      }
      android.util.Log.d("SmsAppHash", "packageName=$packageName signatureCount=${signingInfo?.size ?: -1}")
      signingInfo?.forEach { signature ->
        val hash = hash(packageName, signature.toCharsString())
        android.util.Log.d("SmsAppHash", "computed hash=$hash")
        if (hash != null) signatures.add(hash)
      }
    } catch (e: Exception) {
      android.util.Log.e("SmsAppHash", "getAppSignatures failed", e)
    }
    return signatures
  }

  private fun hash(packageName: String, signature: String): String? {
    val appInfo = "$packageName $signature"
    return try {
      val messageDigest = MessageDigest.getInstance("SHA-256")
      messageDigest.update(appInfo.toByteArray(Charsets.UTF_8))
      var hashSignature = messageDigest.digest()
      hashSignature = hashSignature.copyOfRange(0, 9)
      var base64Hash = Base64.encodeToString(hashSignature, Base64.NO_PADDING or Base64.NO_WRAP)
      base64Hash = base64Hash.substring(0, 11)
      base64Hash
    } catch (_: Exception) {
      null
    }
  }
}

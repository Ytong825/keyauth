// KeyAuth 客户端示例 · C#
//
// 目标框架：.NET Framework 4.6+ / .NET 6+ / .NET 8
// 依赖：无（只用 BCL，不引 Newtonsoft）
//
// 编译：
//   .NET Framework : csc client.cs
//   .NET 6+        : dotnet new console -o demo && 复制本文件覆盖 Program.cs
//
// 用法：
//   demo.exe https://auth.example.com app_xxxxxxxx 你的AppSecret
//
// 注意：示例里用正则取 JSON 字段，够用且零依赖。生产环境建议换成
//       System.Text.Json（.NET 6+）或 Newtonsoft.Json。

using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Win32;

public class KeyAuth
{
    private static readonly HttpClient Http = new HttpClient { Timeout = TimeSpan.FromSeconds(10) };

    private readonly string _base;
    private readonly string _appId;
    private readonly string _secret;
    private readonly string _version;

    public KeyAuth(string baseUrl, string appId, string appSecret, string version = "1.0.0")
    {
        _base = baseUrl.TrimEnd('/');
        _appId = appId;
        _secret = appSecret;
        _version = version;
    }

    // ---------------------------------------------------------------- 机器码
    /// <summary>
    /// 机器码：注册表 MachineGuid + 系统盘卷序列号 + 计算机名。
    /// 原则是「同一台机器每次算出来都一样」，重装系统才会变。
    /// 不要用 MAC 地址——现代系统默认随机化。
    /// </summary>
    public static string MachineId()
    {
        string guid = "";
        try
        {
            using (var k = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Microsoft\Cryptography"))
                if (k != null) guid = (k.GetValue("MachineGuid") ?? "").ToString();
        }
        catch { /* 读不到就用空串兜底，别让程序崩 */ }

        string vol = "";
        try { vol = VolumeSerial("C:\\"); } catch { }

        string raw = guid + "|" + vol + "|" + Environment.MachineName;
        using (var sha = SHA256.Create())
        {
            byte[] h = sha.ComputeHash(Encoding.UTF8.GetBytes(raw));
            return BitConverter.ToString(h).Replace("-", "").Substring(0, 32).ToLowerInvariant();
        }
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    private static extern bool GetVolumeInformation(
        string root, StringBuilder volName, int volNameSize,
        out uint serial, out uint maxLen, out uint flags,
        StringBuilder fsName, int fsNameSize);

    private static string VolumeSerial(string root)
    {
        uint serial, maxLen, flags;
        if (!GetVolumeInformation(root, null, 0, out serial, out maxLen, out flags, null, 0))
            return "";
        return serial.ToString("X8");
    }

    // ---------------------------------------------------------------- 签名
    /// <summary>除 sign 外全部参数参与，按参数名 ASCII 升序，HMAC-SHA256 小写十六进制。</summary>
    public static string Sign(IDictionary<string, string> p, string secret)
    {
        string raw = string.Join("&", p
            .Where(kv => kv.Key != "sign")
            .OrderBy(kv => kv.Key, StringComparer.Ordinal)   // 必须 Ordinal，别用本地化排序
            .Select(kv => kv.Key + "=" + (kv.Value ?? "")));
        using (var h = new HMACSHA256(Encoding.UTF8.GetBytes(secret)))
            return BitConverter.ToString(h.ComputeHash(Encoding.UTF8.GetBytes(raw)))
                .Replace("-", "").ToLowerInvariant();
    }

    private static string ToJson(IDictionary<string, string> p)
    {
        var sb = new StringBuilder("{");
        bool first = true;
        foreach (var kv in p)
        {
            if (!first) sb.Append(',');
            first = false;
            // ts 用数字，其余用字符串（服务端对两者都能解析）
            if (kv.Key == "ts" || kv.Key == "cost")
                sb.Append('"').Append(kv.Key).Append("\":").Append(kv.Value);
            else
                sb.Append('"').Append(kv.Key).Append("\":\"")
                  .Append((kv.Value ?? "").Replace("\\", "\\\\").Replace("\"", "\\\""))
                  .Append('"');
        }
        return sb.Append('}').ToString();
    }

    private Dictionary<string, string> Call(string path, string code, string machine)
    {
        var p = new Dictionary<string, string>
        {
            { "app_id", _appId },
            { "code", code },
            { "machine_id", machine },
            { "ts", DateTimeOffset.UtcNow.ToUnixTimeSeconds().ToString() },
            { "nonce", Guid.NewGuid().ToString("N") },
            { "ver", _version },
        };

        // 先把全部字段（除 sign）算进签名，再把 sign 加进去发送
        p["sign"] = Sign(p, _secret);

        using (var req = new HttpRequestMessage(HttpMethod.Post, _base + path))
        {
            req.Content = new StringContent(ToJson(p), Encoding.UTF8, "application/json");
            try
            {
                using (var resp = Http.SendAsync(req).GetAwaiter().GetResult())
                {
                    string body = resp.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                    return new Dictionary<string, string> { { "__raw", body } };
                }
            }
            catch (Exception ex)
            {
                return new Dictionary<string, string>
                {
                    { "__raw", "{\"ok\":false,\"err\":\"NETWORK\",\"msg\":\"" + ex.Message.Replace("\"", "'") + "\"}" }
                };
            }
        }
    }

    // ---------------------------------------------------------------- 四个接口
    // 用普通方法体而不是 => 表达式体，兼容 .NET Framework 自带的老编译器
    public Result Verify(string code, string machine)
    {
        return Result.Parse(Call("/api/v1/verify", code, machine ?? MachineId())["__raw"]);
    }

    public Result Heartbeat(string code, string machine)
    {
        return Result.Parse(Call("/api/v1/heartbeat", code, machine ?? MachineId())["__raw"]);
    }

    public Result Query(string code, string machine)
    {
        return Result.Parse(Call("/api/v1/query", code, machine ?? MachineId())["__raw"]);
    }

    public Result Unbind(string code, string machine)
    {
        return Result.Parse(Call("/api/v1/unbind", code, machine ?? MachineId())["__raw"]);
    }

    // ---------------------------------------------------------------- 响应
    public class Result
    {
        public bool Ok;
        public string Err, Msg;
        public string Raw;

        // data 里的常用字段
        public string Code, Status, ExpiresText, CardTypeText, Announcement;
        public long RemainingSeconds, Devices, MaxDevices, UnbindLeft, HeartbeatInterval;

        public static Result Parse(string json)
        {
            // 服务端 json.dumps 默认带空格（"ok": true），这里必须容忍空格
            var r = new Result { Raw = json, Ok = Regex.IsMatch(json, "\"ok\"\\s*:\\s*true") };
            if (r.Ok)
            {
                r.Code = Str(json, "code");
                r.Status = Str(json, "status");
                r.ExpiresText = Str(json, "expires_text");
                r.CardTypeText = Str(json, "card_type_text");
                r.Announcement = Str(json, "announcement");
                r.RemainingSeconds = Num(json, "remaining_seconds");
                r.Devices = Num(json, "devices");
                r.MaxDevices = Num(json, "max_devices");
                r.UnbindLeft = Num(json, "unbind_left");
                r.HeartbeatInterval = Num(json, "heartbeat_interval");
            }
            else
            {
                r.Err = Str(json, "err");
                r.Msg = Str(json, "msg");
            }
            return r;
        }

        private static string Str(string json, string key)
        {
            var m = Regex.Match(json, "\"" + Regex.Escape(key) + "\"\\s*:\\s*\"((?:[^\"\\\\]|\\\\.)*)\"");
            return m.Success ? Regex.Unescape(m.Groups[1].Value) : null;
        }

        private static long Num(string json, string key)
        {
            var m = Regex.Match(json, "\"" + Regex.Escape(key) + "\"\\s*:\\s*(-?\\d+)");
            return m.Success ? long.Parse(m.Groups[1].Value) : 0;
        }
    }
}

public static class Program
{
    public static int Main(string[] args)
    {
        if (args.Length < 3)
        {
            Console.WriteLine("用法: client.exe <服务端地址> <AppID> <AppSecret>");
            return 1;
        }

        var ka = new KeyAuth(args[0], args[1], args[2]);
        string machine = KeyAuth.MachineId();
        Console.WriteLine("机器码: " + machine);

        Console.Write("请输入卡密: ");
        string card = (Console.ReadLine() ?? "").Trim();
        if (card.Length == 0) { Console.WriteLine("没有卡密"); return 1; }

        var r = ka.Verify(card, machine);
        if (!r.Ok)
        {
            Console.WriteLine("校验失败 [" + r.Err + "] " + r.Msg);
            return 2;
        }

        Console.WriteLine("到期: " + r.ExpiresText + " | 剩余秒: " + r.RemainingSeconds
            + " | 设备: " + r.Devices + "/" + r.MaxDevices + " | 剩余换绑: " + r.UnbindLeft);

        // 心跳线程：连续 3 次软失败才判定离线，硬失败立即退出
        int interval = (int)(r.HeartbeatInterval > 0 ? r.HeartbeatInterval : 180);
        var th = new Thread(() =>
        {
            int fail = 0;
            while (true)
            {
                Thread.Sleep(interval * 1000);
                var hb = ka.Heartbeat(card, machine);
                if (hb.Ok) { fail = 0; continue; }

                if (hb.Err == "CARD_BANNED" || hb.Err == "CARD_EXPIRED" || hb.Err == "DEVICE_MISMATCH")
                {
                    Console.WriteLine("授权失效 [" + hb.Err + "] " + hb.Msg);
                    Environment.Exit(3);
                }
                if (++fail >= 3) Console.WriteLine("连续 3 次心跳失败，进入离线宽限");
            }
        });
        th.IsBackground = true;
        th.Start();

        Console.WriteLine("按回车退出…");
        Console.ReadLine();
        return 0;
    }
}

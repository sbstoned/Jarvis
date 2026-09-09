using System.Text.Json;
using System.Text.Json.Serialization;
using LibreHardwareMonitor.Hardware;
using System.Security.Principal;

namespace JarvisHardwareSensors;

public sealed record SensorRecord(
    string HardwareName, string HardwareType, string HardwareId,
    string SensorName, string SensorType, string SensorId,
    double Value, string? Unit
);

public sealed class SensorSummary
{
    public double? CpuPackageTempC { get; set; }
    public double? CpuCoreMaxTempC { get; set; }
    public double? GpuCoreTempC { get; set; }
    public double? GpuHotspotTempC { get; set; }
    public double? RamTempC { get; set; }
    public double? MotherboardTempC { get; set; }
    public double? StorageTempC { get; set; }
    public List<double> FanRpm { get; set; } = new();
}

public sealed class SensorPayload
{
    public bool Ok { get; set; }
    public string Source { get; set; } = "JarvisHardwareSensors .NET 10";
    public string? Error { get; set; }
    public DateTimeOffset Timestamp { get; set; } = DateTimeOffset.Now;
    public SensorSummary Summary { get; set; } = new();
    public List<SensorRecord> Sensors { get; set; } = new();
    public bool IsAdministrator { get; set; }
}

internal static class Program
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = false,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase
    };

    private static void UpdateRecursive(IHardware hardware, List<SensorRecord> output)
    {
        try { hardware.Update(); } catch { }

        foreach (var sensor in hardware.Sensors)
        {
            if (sensor.Value is null) continue;

            output.Add(new SensorRecord(
                hardware.Name ?? "",
                hardware.HardwareType.ToString(),
                hardware.Identifier?.ToString() ?? "",
                sensor.Name ?? "",
                sensor.SensorType.ToString(),
                sensor.Identifier?.ToString() ?? "",
                Convert.ToDouble(sensor.Value.Value),
                UnitFor(sensor.SensorType)
            ));
        }

        foreach (var child in hardware.SubHardware)
            UpdateRecursive(child, output);
    }

    private static string? UnitFor(SensorType type) => type switch
    {
        SensorType.Temperature => "°C",
        SensorType.Fan => "RPM",
        SensorType.Load => "%",
        SensorType.Clock => "MHz",
        SensorType.Power => "W",
        SensorType.Voltage => "V",
        SensorType.Data => "GB",
        SensorType.SmallData => "MB",
        SensorType.Throughput => "B/s",
        _ => null
    };

    private static bool ContainsAny(string value, params string[] terms)
        => terms.Any(t => value.Contains(t, StringComparison.OrdinalIgnoreCase));

    private static double? MaxOrNull(IEnumerable<double> values)
    {
        var list = values.ToList();
        return list.Count == 0 ? null : Math.Round(list.Max(), 1);
    }

    private static SensorSummary BuildSummary(List<SensorRecord> sensors)
    {
        var temps = sensors
            .Where(s => s.SensorType.Equals("Temperature", StringComparison.OrdinalIgnoreCase))
            .Where(s => s.Value > -20 && s.Value < 150)
            .ToList();

        var cpuTemps = temps.Where(s =>
            ContainsAny($"{s.HardwareType} {s.HardwareName} {s.HardwareId}", "cpu", "processor")).ToList();

        var cpuPackage = cpuTemps.Where(s =>
            ContainsAny($"{s.SensorName} {s.SensorId}", "package", "tctl", "tdie", "core max"))
            .Select(s => s.Value);

        var gpuTemps = temps.Where(s =>
            ContainsAny($"{s.HardwareType} {s.HardwareName} {s.HardwareId}",
                "gpu", "nvidia", "geforce", "radeon", "graphics")).ToList();

        var gpuCore = gpuTemps.Where(s =>
            !ContainsAny($"{s.SensorName} {s.SensorId}", "hot spot", "hotspot", "junction", "memory"))
            .Select(s => s.Value);

        var gpuHotspot = gpuTemps.Where(s =>
            ContainsAny($"{s.SensorName} {s.SensorId}", "hot spot", "hotspot", "junction"))
            .Select(s => s.Value);

        var ramTemps = temps.Where(s =>
            ContainsAny($"{s.HardwareType} {s.HardwareName} {s.HardwareId} {s.SensorName} {s.SensorId}",
                "memory", "dimm", "dram", "ram", "spd")).Select(s => s.Value);

        var motherboardTemps = temps.Where(s =>
            ContainsAny($"{s.HardwareType} {s.HardwareId}", "motherboard", "/lpc/"))
            .Select(s => s.Value);

        var storageTemps = temps.Where(s =>
            ContainsAny($"{s.HardwareType} {s.HardwareName} {s.HardwareId}", "storage", "nvme", "ssd", "hdd"))
            .Select(s => s.Value);

        var fans = sensors
            .Where(s => s.SensorType.Equals("Fan", StringComparison.OrdinalIgnoreCase))
            .Where(s => s.Value >= 0 && s.Value < 30000)
            .Select(s => Math.Round(s.Value, 0))
            .ToList();

        return new SensorSummary
        {
            CpuPackageTempC = MaxOrNull(cpuPackage.Any() ? cpuPackage : cpuTemps.Select(s => s.Value)),
            CpuCoreMaxTempC = MaxOrNull(cpuTemps.Select(s => s.Value)),
            GpuCoreTempC = MaxOrNull(gpuCore.Any() ? gpuCore : gpuTemps.Select(s => s.Value)),
            GpuHotspotTempC = MaxOrNull(gpuHotspot),
            RamTempC = MaxOrNull(ramTemps),
            MotherboardTempC = MaxOrNull(motherboardTemps),
            StorageTempC = MaxOrNull(storageTemps),
            FanRpm = fans
        };
    }

    private static SensorPayload ReadSnapshot()
    {
        var payload = new SensorPayload();
        try
        {
            using var identity = WindowsIdentity.GetCurrent();
            payload.IsAdministrator = new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator);
        }
        catch { payload.IsAdministrator = false; }

        try
        {
            var computer = new Computer
            {
                IsCpuEnabled = true,
                IsGpuEnabled = true,
                IsMemoryEnabled = true,
                // Motherboard LPC probing can hard-fail on some Windows/.NET 10
                // combinations when System.Management binding differs. CPU/GPU/RAM/
                // storage telemetry does not require that probe, so keep it disabled.
                IsMotherboardEnabled = false,
                IsControllerEnabled = false,
                IsStorageEnabled = true,
                IsNetworkEnabled = false,
                IsPsuEnabled = false
            };
            try
            {
                computer.Open();
                foreach (var hardware in computer.Hardware)
                    UpdateRecursive(hardware, payload.Sensors);
                payload.Summary = BuildSummary(payload.Sensors);
                payload.Ok = true;
            }
            finally
            {
                try { computer.Close(); } catch { }
            }
        }
        catch (Exception ex)
        {
            payload.Ok = false;
            payload.Error = ex.ToString();
        }
        return payload;
    }

    private static void WriteJsonFile(string path, SensorPayload payload)
    {
        var json = JsonSerializer.Serialize(payload, JsonOptions);
        var temp = path + ".tmp";
        File.WriteAllText(temp, json);
        File.Move(temp, path, true);
    }

    public static int Main(string[] args)
    {
        if (args.Length >= 2 && args[0].Equals("--watch", StringComparison.OrdinalIgnoreCase))
        {
            var path = Path.GetFullPath(args[1]);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            while (true)
            {
                var payload = ReadSnapshot();
                try { WriteJsonFile(path, payload); } catch { }
                Thread.Sleep(3000);
            }
        }

        var snapshot = ReadSnapshot();
        Console.WriteLine(JsonSerializer.Serialize(snapshot, JsonOptions));
        return snapshot.Ok ? 0 : 1;
    }

}

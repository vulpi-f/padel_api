// Simple BLE notify listener for Windows using Windows.Devices.Bluetooth
// Goal: more stability than Bleak on WinRT by using raw WinRT APIs.
// Build (needs .NET 6+ SDK):
//   dotnet new console -n BleBridgeWinTmp
//   Replace Program.cs with this file content or add this file to the project.
//   dotnet run -- BLE_TARGET_ADDRESS=16:11:28:03:1C:81 BLE_NOTIFY_CHAR_UUID=00001c0f-d102-11e1-9b23-000efb0000b2

using System;
using System.Globalization;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Windows.Devices.Bluetooth;
using Windows.Devices.Bluetooth.GenericAttributeProfile;
using Windows.Storage.Streams;

class BleBridgeWin
{
    static string TargetMac = Environment.GetEnvironmentVariable("BLE_TARGET_ADDRESS") ?? "16:11:28:03:1C:81";
    static Guid NotifyCharUuid = Guid.Parse(Environment.GetEnvironmentVariable("BLE_NOTIFY_CHAR_UUID") ?? "00001c0f-d102-11e1-9b23-000efb0000b2");
    static TimeSpan RetryDelay = TimeSpan.FromSeconds(double.TryParse(Environment.GetEnvironmentVariable("BLE_RETRY_DELAY"), out var d) ? d : 1.0);

    static async Task<int> Main()
    {
        Console.WriteLine("BLE listener (WinRT API). Target {0}, Notify {1}", TargetMac, NotifyCharUuid);
        var cts = new CancellationTokenSource();
        Console.CancelKeyPress += (s, e) =>
        {
            e.Cancel = true;
            cts.Cancel();
        };

        while (!cts.IsCancellationRequested)
        {
            try
            {
                var device = await ConnectDevice(TargetMac);
                if (device == null)
                {
                    await Task.Delay(RetryDelay, cts.Token);
                    continue;
                }

                var characteristic = await FindNotifyCharacteristic(device, NotifyCharUuid);
                if (characteristic == null)
                    throw new Exception("Notify characteristic not found");

                characteristic.ValueChanged += OnValueChanged;
                var status = await characteristic.WriteClientCharacteristicConfigurationDescriptorAsync(GattClientCharacteristicConfigurationDescriptorValue.Notify);
                if (status != GattCommunicationStatus.Success)
                    throw new Exception($"Enable notify failed: {status}");

                Console.WriteLine("Listening... (CTRL+C to stop)");
                while (!cts.IsCancellationRequested && device.ConnectionStatus == BluetoothConnectionStatus.Connected)
                    await Task.Delay(200, cts.Token);

                Console.WriteLine("Connection lost, retrying...");
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                Console.WriteLine("Error: {0}", ex.Message);
            }
            await Task.Delay(RetryDelay, cts.Token);
        }

        return 0;
    }

    static async Task<BluetoothLEDevice?> ConnectDevice(string mac)
    {
        try
        {
            var addr = ulong.Parse(mac.Replace(":", "").Replace("-", ""), NumberStyles.HexNumber);
            var dev = await BluetoothLEDevice.FromBluetoothAddressAsync(addr);
            if (dev == null)
            {
                Console.WriteLine("Device not found");
                return null;
            }
            if (dev.ConnectionStatus != BluetoothConnectionStatus.Connected)
            {
                // Attempt to cache services; sometimes triggers connection
                await dev.GetGattServicesAsync(BluetoothCacheMode.Uncached);
            }
            Console.WriteLine("Connected to {0}", dev.Name ?? "device");
            return dev;
        }
        catch (Exception ex)
        {
            Console.WriteLine("Connect failed: {0}", ex.Message);
            return null;
        }
    }

    static async Task<GattCharacteristic?> FindNotifyCharacteristic(BluetoothLEDevice dev, Guid preferred)
    {
        var servicesResult = await dev.GetGattServicesAsync(BluetoothCacheMode.Uncached);
        if (servicesResult.Status != GattCommunicationStatus.Success)
            return null;

        foreach (var svc in servicesResult.Services)
        {
            var charsResult = await svc.GetCharacteristicsAsync(BluetoothCacheMode.Uncached);
            if (charsResult.Status != GattCommunicationStatus.Success)
                continue;

            var match = charsResult.Characteristics.FirstOrDefault(c => c.Uuid == preferred && c.CharacteristicProperties.HasFlag(GattCharacteristicProperties.Notify));
            if (match != null)
                return match;

            var anyNotify = charsResult.Characteristics.FirstOrDefault(c => c.CharacteristicProperties.HasFlag(GattCharacteristicProperties.Notify));
            if (anyNotify != null)
                return anyNotify;
        }
        return null;
    }

    static void OnValueChanged(GattCharacteristic sender, GattValueChangedEventArgs args)
    {
        try
        {
            using var reader = DataReader.FromBuffer(args.CharacteristicValue);
            byte[] data = new byte[reader.UnconsumedBufferLength];
            reader.ReadBytes(data);
            Console.WriteLine("[BLE] {0} : {1}", sender.Uuid, BitConverter.ToString(data));
        }
        catch (Exception ex)
        {
            Console.WriteLine("Parse error: {0}", ex.Message);
        }
    }
}

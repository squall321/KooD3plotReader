using Avalonia;
using Avalonia.ReactiveUI;
using System;
using System.IO;
using System.Threading.Tasks;

namespace KooD3plotViewer;

class Program
{
    private static readonly string LogPath = Path.Combine(
        Path.GetDirectoryName(typeof(Program).Assembly.Location) ?? ".",
        "crash.log");

    [STAThread]
    public static void Main(string[] args)
    {
        // Global exception handlers
        AppDomain.CurrentDomain.UnhandledException += (s, e) =>
        {
            LogCrash("AppDomain.UnhandledException", e.ExceptionObject as Exception);
        };

        TaskScheduler.UnobservedTaskException += (s, e) =>
        {
            LogCrash("TaskScheduler.UnobservedTaskException", e.Exception);
            e.SetObserved(); // Prevent crash
        };

        try
        {
            BuildAvaloniaApp().StartWithClassicDesktopLifetime(args);
        }
        catch (Exception ex)
        {
            LogCrash("Main", ex);
            throw;
        }
    }

    private static void LogCrash(string source, Exception? ex)
    {
        try
        {
            var msg = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {source}: {ex?.GetType().Name}: {ex?.Message}\n{ex?.StackTrace}\n\n";
            File.AppendAllText(LogPath, msg);
            Console.Error.WriteLine(msg);
        }
        catch { }
    }

    public static AppBuilder BuildAvaloniaApp()
        => AppBuilder.Configure<App>()
            .UsePlatformDetect()
            .WithInterFont()
            .LogToTrace()
            .UseReactiveUI();
}

using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Media.Effects;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using Brushes = System.Windows.Media.Brushes;
using Button = System.Windows.Controls.Button;
using TextBox = System.Windows.Controls.TextBox;
using WpfApplication = System.Windows.Application;

namespace GPT2JSON.Uninstall
{
    internal static class Program
    {
        [STAThread]
        private static void Main(string[] args)
        {
            bool runFromTemp = HasArg(args, "--run");
            bool silent = HasArg(args, "/silent") || HasArg(args, "/verysilent") || HasArg(args, "--silent");
            string appDir = ValueAfter(args, "--run");
            if (string.IsNullOrWhiteSpace(appDir)) appDir = AppDomain.CurrentDomain.BaseDirectory;

            if (!runFromTemp)
            {
                RelaunchFromTemp(appDir, silent);
                return;
            }

            if (silent)
            {
                Environment.Exit(RunUninstaller(appDir));
                return;
            }

            var app = new WpfApplication();
            app.Run(new UninstallWindow(appDir));
        }

        private static bool HasArg(string[] args, string name)
        {
            return args.Any(a => string.Equals(a, name, StringComparison.OrdinalIgnoreCase));
        }

        private static string ValueAfter(string[] args, string name)
        {
            for (int i = 0; i < args.Length - 1; i++)
                if (string.Equals(args[i], name, StringComparison.OrdinalIgnoreCase))
                    return args[i + 1];
            return string.Empty;
        }

        private static void RelaunchFromTemp(string appDir, bool silent)
        {
            try
            {
                string tempDir = Path.Combine(Path.GetTempPath(), "GPT2JSON-Uninstall", Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(tempDir);
                string target = Path.Combine(tempDir, "GPT2JSON-Uninstall.exe");
                File.Copy(Assembly.GetExecutingAssembly().Location, target, true);
                string args = "--run \"" + appDir.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + "\"";
                if (silent) args += " /silent";
                Process.Start(new ProcessStartInfo
                {
                    FileName = target,
                    Arguments = args,
                    UseShellExecute = false,
                    WorkingDirectory = tempDir
                });
            }
            catch
            {
                RunUninstaller(appDir);
            }
        }

        internal static int RunUninstaller(string appDir)
        {
            string uninstaller = FindInnoUninstaller(appDir);
            if (string.IsNullOrWhiteSpace(uninstaller)) return 2;

            var psi = new ProcessStartInfo
            {
                FileName = uninstaller,
                Arguments = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART",
                UseShellExecute = false,
                CreateNoWindow = true,
                WorkingDirectory = appDir
            };
            var process = Process.Start(psi);
            process.WaitForExit();
            return process.ExitCode;
        }

        internal static string FindInnoUninstaller(string appDir)
        {
            if (string.IsNullOrWhiteSpace(appDir) || !Directory.Exists(appDir)) return string.Empty;
            string preferred = Path.Combine(appDir, ".uninstall", "unins000.exe");
            if (File.Exists(preferred)) return preferred;
            preferred = Path.Combine(appDir, "unins000.exe");
            if (File.Exists(preferred)) return preferred;
            string privateDir = Path.Combine(appDir, ".uninstall");
            if (Directory.Exists(privateDir))
            {
                string privateMatch = Directory.GetFiles(privateDir, "unins*.exe").OrderBy(p => p, StringComparer.OrdinalIgnoreCase).FirstOrDefault();
                if (!string.IsNullOrWhiteSpace(privateMatch)) return privateMatch;
            }
            return Directory.GetFiles(appDir, "unins*.exe").OrderBy(p => p, StringComparer.OrdinalIgnoreCase).FirstOrDefault() ?? string.Empty;
        }
    }

    public sealed class UninstallWindow : Window
    {
        private const string AppName = "GPT2JSON";
        private const string AppVersion = "0.0.0";
        private const string Version = "v" + AppVersion;
        private readonly string _appDir;
        private readonly Button _mainButton;
        private readonly Button _secondaryButton;
        private readonly ElegantProgressBar _progress;
        private readonly TextBlock _status;
        private bool _done;

        public UninstallWindow(string appDir)
        {
            _appDir = appDir;
            Title = AppName + " " + Version + " 卸载";
            Width = 1120;
            Height = 640;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;
            WindowStyle = WindowStyle.None;
            AllowsTransparency = true;
            ResizeMode = ResizeMode.NoResize;
            Background = Brushes.Transparent;
            Icon = LoadImage("GPT2JSON.Icon.png");
            SnapsToDevicePixels = true;
            UseLayoutRounding = true;

            var root = new Canvas { Width = 1120, Height = 640 };
            Content = root;

            var shellArt = new Image
            {
                Width = 1040,
                Height = 560,
                Source = LoadImage("GPT2JSON.ShellArt.png"),
                Stretch = Stretch.Fill,
                IsHitTestVisible = false,
                Effect = new DropShadowEffect { BlurRadius = 30, ShadowDepth = 0, Opacity = 0.42, Color = Color.FromRgb(0, 0, 0) }
            };
            Motion.PrepareEntrance(shellArt, 10, 0.985);
            Canvas.SetLeft(shellArt, 40);
            Canvas.SetTop(shellArt, 40);
            root.Children.Add(shellArt);

            var shell = new Grid { Width = 1040, Height = 560, Clip = ShellSurfaceGeometry(), Background = Brushes.Transparent };
            Motion.PrepareEntrance(shell, 8, 0.992);
            Canvas.SetLeft(shell, 40);
            Canvas.SetTop(shell, 40);
            root.Children.Add(shell);
            shell.MouseLeftButtonDown += delegate(object sender, MouseButtonEventArgs e)
            {
                if (e.ChangedButton == MouseButton.Left)
                {
                    try { DragMove(); } catch { }
                }
            };

            AddFlow(shell);
            AddBrand(shell);
            var overlay = new Canvas { Width = 1040, Height = 560 };
            shell.Children.Add(overlay);

            var windowButtons = new StackPanel { Orientation = System.Windows.Controls.Orientation.Horizontal };
            var min = WindowButton("—");
            var close = WindowButton("×");
            min.Click += delegate { WindowState = WindowState.Minimized; };
            close.Click += delegate { Close(); };
            windowButtons.Children.Add(min);
            windowButtons.Children.Add(close);
            Canvas.SetLeft(windowButtons, 848);
            Canvas.SetTop(windowButtons, 82);
            overlay.Children.Add(windowButtons);

            var title = new TextBlock
            {
                Text = "卸载",
                Foreground = Brushes.White,
                FontSize = 43,
                FontWeight = FontWeights.Bold,
                Effect = new DropShadowEffect { BlurRadius = 18, ShadowDepth = 0, Color = Color.FromRgb(43, 137, 255), Opacity = 0.18 }
            };
            Canvas.SetLeft(title, 410);
            Canvas.SetTop(title, 154);
            overlay.Children.Add(title);

            var desc = new TextBlock
            {
                Text = "将移除程序文件与快捷方式，账号与导出文件不会被安装器主动删除。",
                Foreground = new SolidColorBrush(Color.FromRgb(166, 187, 220)),
                FontSize = 14,
                TextWrapping = TextWrapping.Wrap,
                Width = 560
            };
            Canvas.SetLeft(desc, 412);
            Canvas.SetTop(desc, 226);
            overlay.Children.Add(desc);

            var label = new TextBlock
            {
                Text = "卸载位置",
                Foreground = new SolidColorBrush(Color.FromRgb(231, 240, 255)),
                FontSize = 15,
                FontWeight = FontWeights.SemiBold
            };
            Canvas.SetLeft(label, 410);
            Canvas.SetTop(label, 292);
            overlay.Children.Add(label);

            var pathBorder = new Border
            {
                Width = 568,
                Height = 58,
                CornerRadius = new CornerRadius(18),
                Background = new SolidColorBrush(Color.FromArgb(48, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(85, 142, 195, 255)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(18, 0, 18, 0),
                Child = new TextBox
                {
                    Text = _appDir,
                    Foreground = new SolidColorBrush(Color.FromRgb(225, 238, 255)),
                    Background = Brushes.Transparent,
                    BorderThickness = new Thickness(0),
                    FontSize = 15,
                    IsReadOnly = true,
                    VerticalContentAlignment = System.Windows.VerticalAlignment.Center,
                    CaretBrush = Brushes.White
                }
            };
            Canvas.SetLeft(pathBorder, 410);
            Canvas.SetTop(pathBorder, 326);
            overlay.Children.Add(pathBorder);

            _progress = new ElegantProgressBar { Width = 568, Height = 9, Value = 0 };
            Canvas.SetLeft(_progress, 410);
            Canvas.SetTop(_progress, 395);
            overlay.Children.Add(_progress);

            _status = new TextBlock
            {
                Text = "准备就绪：点击卸载即可开始。",
                Foreground = new SolidColorBrush(Color.FromRgb(137, 158, 196)),
                FontSize = 12
            };
            Canvas.SetLeft(_status, 412);
            Canvas.SetTop(_status, 412);
            overlay.Children.Add(_status);

            _mainButton = new Button
            {
                Content = "卸载",
                Width = 172,
                Height = 54,
                FontSize = 17,
                FontWeight = FontWeights.Bold,
                Foreground = Brushes.White,
                Background = new LinearGradientBrush(Color.FromRgb(27, 181, 255), Color.FromRgb(176, 69, 255), 0),
                BorderBrush = new SolidColorBrush(Color.FromArgb(135, 202, 232, 255)),
                Style = RoundedButtonStyle(18)
            };
            _mainButton.Click += async delegate
            {
                if (_done) { Close(); return; }
                await UninstallAsync();
            };
            Canvas.SetLeft(_mainButton, 655);
            Canvas.SetTop(_mainButton, 434);
            overlay.Children.Add(_mainButton);

            _secondaryButton = new Button
            {
                Content = "取消",
                Width = 132,
                Height = 54,
                FontSize = 15,
                Foreground = new SolidColorBrush(Color.FromRgb(218, 230, 255)),
                Background = new SolidColorBrush(Color.FromArgb(28, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(86, 163, 190, 255)),
                Style = RoundedButtonStyle(18)
            };
            _secondaryButton.Click += delegate { Close(); };
            Canvas.SetLeft(_secondaryButton, 850);
            Canvas.SetTop(_secondaryButton, 434);
            overlay.Children.Add(_secondaryButton);

            Loaded += delegate
            {
                Motion.PlayEntrance(shellArt, 0);
                Motion.PlayEntrance(shell, 120);
                Motion.PulseDropShadow(shellArt.Effect as DropShadowEffect, 0.34, 0.52, 3200, 600);
            };
        }

        private async Task UninstallAsync()
        {
            _mainButton.IsEnabled = false;
            _secondaryButton.IsEnabled = false;
            _status.Text = "正在准备卸载核心…";
            Motion.AnimateProgress(_progress, 18);

            int code = await Task.Run(delegate
            {
                System.Threading.Thread.Sleep(240);
                Dispatcher.Invoke(delegate
                {
                    _status.Text = "正在移除程序文件与快捷方式…";
                    Motion.AnimateProgress(_progress, 62);
                });
                return Program.RunUninstaller(_appDir);
            });

            if (code == 0)
            {
                _done = true;
                _status.Text = "卸载完成：GPT2JSON 已移除。";
                Motion.AnimateProgress(_progress, 100);
                _mainButton.Content = "完成";
                _mainButton.IsEnabled = true;
                _secondaryButton.Content = "关闭";
                _secondaryButton.IsEnabled = true;
            }
            else
            {
                _status.Text = "卸载失败：卸载核心返回错误码 " + code;
                Motion.AnimateProgress(_progress, 0);
                _mainButton.IsEnabled = true;
                _secondaryButton.IsEnabled = true;
            }
        }

        private void AddBrand(Grid shell)
        {
            shell.Children.Add(new TextBlock
            {
                Text = AppName,
                Foreground = Brushes.White,
                FontSize = 38,
                FontWeight = FontWeights.Bold,
                Margin = new Thickness(95, 306, 0, 0),
                Effect = new DropShadowEffect { BlurRadius = 18, ShadowDepth = 0, Color = Color.FromRgb(35, 162, 255), Opacity = 0.28 }
            });
            shell.Children.Add(new TextBlock
            {
                Text = "Sub2API / CPA JSON 导出工具",
                Foreground = new SolidColorBrush(Color.FromRgb(184, 205, 236)),
                FontSize = 14,
                Margin = new Thickness(103, 354, 0, 0)
            });
            shell.Children.Add(new Border
            {
                CornerRadius = new CornerRadius(12),
                Background = new SolidColorBrush(Color.FromArgb(45, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(80, 255, 255, 255)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(12, 5, 12, 5),
                HorizontalAlignment = System.Windows.HorizontalAlignment.Left,
                VerticalAlignment = System.Windows.VerticalAlignment.Bottom,
                Margin = new Thickness(114, 0, 0, 52),
                Child = new TextBlock { Text = Version, Foreground = new SolidColorBrush(Color.FromRgb(210, 225, 255)), FontSize = 13, FontWeight = FontWeights.SemiBold }
            });
        }

        private void AddFlow(Grid shell)
        {
            shell.Children.Add(new CurveFlowLayer
            {
                Width = 1040,
                Height = 560,
                IsHitTestVisible = false,
                Opacity = 0.96
            });
        }

        private Geometry ShellSurfaceGeometry()
        {
            return new CombinedGeometry(GeometryCombineMode.Exclude, OuterShellGeometry(), VoidHoleGeometry());
        }

        private Geometry OuterShellGeometry()
        {
            return Geometry.Parse("M96,7 C53,0 23,28 17,78 C10,132 48,164 29,225 C12,292 -4,338 34,397 C72,456 34,504 82,535 C130,568 202,548 274,550 C370,554 446,528 514,510 C612,485 704,517 802,544 L970,544 C1018,544 1040,514 1040,466 L1040,84 C1040,34 1008,8 958,8 L790,8 C712,8 662,48 560,30 C500,19 453,18 382,44 C328,66 280,48 224,24 C178,8 143,15 96,7 Z");
        }

        private Geometry VoidHoleGeometry()
        {
            return Geometry.Parse("M665,82 C670,48 710,25 763,30 C812,35 842,62 838,96 C834,132 788,151 735,146 C690,142 662,116 665,82 Z");
        }

        private Button WindowButton(string text)
        {
            return new Button
            {
                Content = text,
                Width = 42,
                Height = 34,
                Margin = new Thickness(7, 0, 0, 0),
                Foreground = new SolidColorBrush(Color.FromRgb(217, 229, 255)),
                Background = new SolidColorBrush(Color.FromArgb(32, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(45, 255, 255, 255)),
                FontSize = text == "×" ? 20 : 15,
                Style = RoundedButtonStyle(17)
            };
        }

        internal static Style RoundedButtonStyle(double radius)
        {
            var style = new Style(typeof(Button));
            var border = new FrameworkElementFactory(typeof(Border));
            border.SetValue(Border.CornerRadiusProperty, new CornerRadius(radius));
            border.SetValue(Border.BackgroundProperty, new TemplateBindingExtension(Button.BackgroundProperty));
            border.SetValue(Border.BorderBrushProperty, new TemplateBindingExtension(Button.BorderBrushProperty));
            border.SetValue(Border.BorderThicknessProperty, new TemplateBindingExtension(Button.BorderThicknessProperty));
            var content = new FrameworkElementFactory(typeof(ContentPresenter));
            content.SetValue(ContentPresenter.HorizontalAlignmentProperty, System.Windows.HorizontalAlignment.Center);
            content.SetValue(ContentPresenter.VerticalAlignmentProperty, System.Windows.VerticalAlignment.Center);
            border.AppendChild(content);
            var template = new ControlTemplate(typeof(Button));
            template.VisualTree = border;
            style.Setters.Add(new Setter(Button.TemplateProperty, template));
            style.Setters.Add(new Setter(Button.CursorProperty, System.Windows.Input.Cursors.Hand));
            style.Setters.Add(new Setter(Button.PaddingProperty, new Thickness(10, 0, 10, 0)));
            style.Setters.Add(new EventSetter(UIElement.MouseEnterEvent, new MouseEventHandler(Motion.ButtonMouseEnter)));
            style.Setters.Add(new EventSetter(UIElement.MouseLeaveEvent, new MouseEventHandler(Motion.ButtonMouseLeave)));
            style.Setters.Add(new EventSetter(UIElement.PreviewMouseLeftButtonDownEvent, new MouseButtonEventHandler(Motion.ButtonMouseDown)));
            style.Setters.Add(new EventSetter(UIElement.PreviewMouseLeftButtonUpEvent, new MouseButtonEventHandler(Motion.ButtonMouseUp)));
            return style;
        }

        private BitmapImage LoadImage(string resourceName)
        {
            using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(resourceName))
            {
                if (stream == null) return null;
                var memory = new MemoryStream();
                stream.CopyTo(memory);
                memory.Position = 0;
                var image = new BitmapImage();
                image.BeginInit();
                image.CacheOption = BitmapCacheOption.OnLoad;
                image.StreamSource = memory;
                image.EndInit();
                image.Freeze();
                return image;
            }
        }
    }

    internal sealed class CurveFlowLayer : FrameworkElement
    {
        private sealed class Curve
        {
            public Point P0;
            public Point P1;
            public Point P2;
            public Point P3;
            public Color Core;
            public Color Halo;
            public double Width;
            public double Offset;
            public double Speed;
        }

        private static readonly Point LogoCenter = new Point(184, 188);
        private const double LogoRadiusX = 124;
        private const double LogoRadiusY = 112;
        private readonly Curve[] _curves;
        private readonly DispatcherTimer _timer;
        private double _phase;

        public CurveFlowLayer()
        {
            // Coordinates are in the 1040x560 shell coordinate system.  The
            // curves intentionally follow the left artwork's existing S-shaped
            // light trails and move from bottom to top, rather than drifting as
            // straight ribbons.  End points stay inside the safe art island so
            // the transparent window edge does not hard-clip the glow.
            _curves = new[]
            {
                new Curve
                {
                    P0 = new Point(74, 468), P1 = new Point(24, 400), P2 = new Point(70, 308), P3 = new Point(54, 216),
                    Core = Color.FromRgb(43, 219, 255), Halo = Color.FromRgb(62, 104, 255), Width = 2.4, Offset = 0.02, Speed = 0.76
                },
                new Curve
                {
                    P0 = new Point(292, 462), P1 = new Point(174, 386), P2 = new Point(226, 282), P3 = new Point(304, 76),
                    Core = Color.FromRgb(188, 70, 255), Halo = Color.FromRgb(42, 204, 255), Width = 3.0, Offset = 0.24, Speed = 0.62
                },
                new Curve
                {
                    P0 = new Point(214, 452), P1 = new Point(158, 392), P2 = new Point(202, 330), P3 = new Point(270, 254),
                    Core = Color.FromRgb(38, 196, 255), Halo = Color.FromRgb(170, 72, 255), Width = 1.9, Offset = 0.46, Speed = 0.70
                },
                new Curve
                {
                    P0 = new Point(252, 336), P1 = new Point(326, 258), P2 = new Point(274, 168), P3 = new Point(324, 78),
                    Core = Color.FromRgb(158, 88, 255), Halo = Color.FromRgb(46, 203, 255), Width = 2.1, Offset = 0.66, Speed = 0.56
                },
                new Curve
                {
                    P0 = new Point(120, 486), P1 = new Point(178, 522), P2 = new Point(314, 482), P3 = new Point(476, 506),
                    Core = Color.FromRgb(48, 214, 255), Halo = Color.FromRgb(184, 79, 255), Width = 1.8, Offset = 0.84, Speed = 0.44
                }
            };

            _timer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(24) };
            _timer.Tick += delegate
            {
                _phase += 0.0068;
                if (_phase > 1) _phase -= 1;
                InvalidateVisual();
            };
            Loaded += delegate { _timer.Start(); };
            Unloaded += delegate { _timer.Stop(); };
        }

        protected override void OnRender(DrawingContext dc)
        {
            base.OnRender(dc);

            for (int i = 0; i < _curves.Length; i++)
            {
                DrawBaseCurve(dc, _curves[i]);
                DrawComet(dc, _curves[i]);
            }
        }

        private void DrawBaseCurve(DrawingContext dc, Curve curve)
        {
            const int segments = 92;
            for (int i = 0; i < segments; i++)
            {
                double t1 = (double)i / segments;
                double t2 = (double)(i + 1) / segments;
                Point a = Sample(curve, t1);
                Point b = Sample(curve, t2);
                if (IsLogoProtected(Mid(a, b))) continue;

                var haloPen = new Pen(new SolidColorBrush(Color.FromArgb(18, curve.Halo.R, curve.Halo.G, curve.Halo.B)), curve.Width + 4.6);
                haloPen.StartLineCap = PenLineCap.Round;
                haloPen.EndLineCap = PenLineCap.Round;
                dc.DrawLine(haloPen, a, b);

                var corePen = new Pen(new SolidColorBrush(Color.FromArgb(34, curve.Core.R, curve.Core.G, curve.Core.B)), curve.Width);
                corePen.StartLineCap = PenLineCap.Round;
                corePen.EndLineCap = PenLineCap.Round;
                dc.DrawLine(corePen, a, b);
            }
        }

        private void DrawComet(DrawingContext dc, Curve curve)
        {
            // Curves are defined from bottom to top.  Increasing t therefore
            // makes the head climb along the same direction as the source art.
            double head = Wrap(_phase * curve.Speed + curve.Offset);
            const int segments = 26;
            const double step = 0.0085;

            for (int i = segments; i >= 1; i--)
            {
                double t1 = Wrap(head - i * step);
                double t2 = Wrap(head - (i - 1) * step);
                if (Math.Abs(t2 - t1) > 0.2) continue;

                Point a = Sample(curve, t1);
                Point b = Sample(curve, t2);
                if (IsLogoProtected(Mid(a, b))) continue;

                double fade = 1.0 - (double)i / segments;
                byte haloAlpha = (byte)(18 + 100 * fade);
                byte coreAlpha = (byte)(36 + 180 * fade);

                var haloPen = new Pen(new SolidColorBrush(Color.FromArgb(haloAlpha, curve.Halo.R, curve.Halo.G, curve.Halo.B)), curve.Width + 7.5 * fade);
                haloPen.StartLineCap = PenLineCap.Round;
                haloPen.EndLineCap = PenLineCap.Round;
                dc.DrawLine(haloPen, a, b);

                var corePen = new Pen(new SolidColorBrush(Color.FromArgb(coreAlpha, curve.Core.R, curve.Core.G, curve.Core.B)), curve.Width + 1.5 * fade);
                corePen.StartLineCap = PenLineCap.Round;
                corePen.EndLineCap = PenLineCap.Round;
                dc.DrawLine(corePen, a, b);
            }

            Point p = Sample(curve, head);
            if (IsLogoProtected(p)) return;
            dc.DrawEllipse(new SolidColorBrush(Color.FromArgb(58, curve.Halo.R, curve.Halo.G, curve.Halo.B)), null, p, curve.Width + 7.0, curve.Width + 7.0);
            dc.DrawEllipse(new SolidColorBrush(Color.FromArgb(220, 255, 255, 255)), null, p, curve.Width + 1.2, curve.Width + 1.2);
            dc.DrawEllipse(new SolidColorBrush(Color.FromArgb(236, curve.Core.R, curve.Core.G, curve.Core.B)), null, p, curve.Width, curve.Width);
        }

        private static bool IsLogoProtected(Point p)
        {
            double dx = (p.X - LogoCenter.X) / LogoRadiusX;
            double dy = (p.Y - LogoCenter.Y) / LogoRadiusY;
            return dx * dx + dy * dy < 1.0;
        }

        private static Point Mid(Point a, Point b)
        {
            return new Point((a.X + b.X) / 2.0, (a.Y + b.Y) / 2.0);
        }

        private static Point Sample(Curve curve, double t)
        {
            double u = 1 - t;
            double x = u * u * u * curve.P0.X + 3 * u * u * t * curve.P1.X + 3 * u * t * t * curve.P2.X + t * t * t * curve.P3.X;
            double y = u * u * u * curve.P0.Y + 3 * u * u * t * curve.P1.Y + 3 * u * t * t * curve.P2.Y + t * t * t * curve.P3.Y;
            return new Point(x, y);
        }

        private static double Wrap(double value)
        {
            value = value - Math.Floor(value);
            if (value < 0) value += 1;
            return value;
        }
    }

    internal sealed class ElegantProgressBar : FrameworkElement
    {
        public static readonly DependencyProperty ValueProperty = DependencyProperty.Register("Value", typeof(double), typeof(ElegantProgressBar), new FrameworkPropertyMetadata(0.0, FrameworkPropertyMetadataOptions.AffectsRender));
        private readonly DispatcherTimer _timer;
        private double _phase;
        public double Value { get { return (double)GetValue(ValueProperty); } set { SetValue(ValueProperty, Math.Max(0, Math.Min(100, value))); } }
        public ElegantProgressBar()
        {
            _timer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(24) };
            _timer.Tick += delegate { _phase += 7.5; if (_phase > Math.Max(ActualWidth, 1) + 160) _phase = 0; InvalidateVisual(); };
            Loaded += delegate { _timer.Start(); };
            Unloaded += delegate { _timer.Stop(); };
        }
        protected override void OnRender(DrawingContext dc)
        {
            double width = ActualWidth, height = ActualHeight;
            if (width <= 0 || height <= 0) return;
            double r = height / 2;
            var track = new Rect(0, 0, width, height);
            dc.DrawRoundedRectangle(new SolidColorBrush(Color.FromArgb(34, 255, 255, 255)), null, track, r, r);
            double fillWidth = Math.Max(0, Math.Min(width, width * Value / 100.0));
            if (fillWidth <= 0.1) return;
            var fill = new LinearGradientBrush { StartPoint = new Point(0, 0.5), EndPoint = new Point(1, 0.5) };
            fill.GradientStops.Add(new GradientStop(Color.FromRgb(29, 190, 255), 0));
            fill.GradientStops.Add(new GradientStop(Color.FromRgb(111, 119, 255), 0.55));
            fill.GradientStops.Add(new GradientStop(Color.FromRgb(193, 74, 255), 1));
            var fillRect = new Rect(0, 0, fillWidth, height);
            dc.DrawRoundedRectangle(fill, null, fillRect, r, r);
            dc.PushClip(new RectangleGeometry(fillRect, r, r));
            var shimmer = new LinearGradientBrush { StartPoint = new Point(0, 0.5), EndPoint = new Point(1, 0.5) };
            shimmer.GradientStops.Add(new GradientStop(Color.FromArgb(0, 255, 255, 255), 0));
            shimmer.GradientStops.Add(new GradientStop(Color.FromArgb(95, 255, 255, 255), 0.48));
            shimmer.GradientStops.Add(new GradientStop(Color.FromArgb(0, 255, 255, 255), 1));
            dc.DrawRectangle(shimmer, null, new Rect(_phase - 110, 0, 90, height));
            dc.Pop();
        }
    }

    internal static class Motion
    {
        private static IEasingFunction EaseOut() { return new CubicEase { EasingMode = EasingMode.EaseOut }; }
        private static DoubleAnimation Tween(double to, int milliseconds, int delayMilliseconds)
        {
            var animation = new DoubleAnimation(to, TimeSpan.FromMilliseconds(milliseconds)) { EasingFunction = EaseOut() };
            if (delayMilliseconds > 0) animation.BeginTime = TimeSpan.FromMilliseconds(delayMilliseconds);
            return animation;
        }
        internal static void PrepareEntrance(FrameworkElement element, double offsetY, double scale)
        {
            if (element == null) return;
            var group = new TransformGroup();
            group.Children.Add(new ScaleTransform(scale, scale));
            group.Children.Add(new TranslateTransform(0, offsetY));
            element.Opacity = 0;
            element.RenderTransformOrigin = new Point(0.5, 0.5);
            element.RenderTransform = group;
        }
        internal static void PlayEntrance(FrameworkElement element, int delayMilliseconds)
        {
            if (element == null) return;
            element.BeginAnimation(UIElement.OpacityProperty, Tween(1, 420, delayMilliseconds));
            var group = element.RenderTransform as TransformGroup;
            if (group == null || group.Children.Count < 2) return;
            var scale = group.Children[0] as ScaleTransform;
            if (scale != null)
            {
                scale.BeginAnimation(ScaleTransform.ScaleXProperty, Tween(1, 520, delayMilliseconds));
                scale.BeginAnimation(ScaleTransform.ScaleYProperty, Tween(1, 520, delayMilliseconds));
            }
            var translate = group.Children[1] as TranslateTransform;
            if (translate != null) translate.BeginAnimation(TranslateTransform.YProperty, Tween(0, 520, delayMilliseconds));
        }
        internal static void PulseDropShadow(DropShadowEffect effect, double from, double to, int milliseconds, int delayMilliseconds)
        {
            if (effect == null) return;
            effect.Opacity = from;
            var animation = new DoubleAnimation(to, TimeSpan.FromMilliseconds(milliseconds)) { BeginTime = TimeSpan.FromMilliseconds(delayMilliseconds), AutoReverse = true, RepeatBehavior = RepeatBehavior.Forever, EasingFunction = new SineEase { EasingMode = EasingMode.EaseInOut } };
            effect.BeginAnimation(DropShadowEffect.OpacityProperty, animation);
        }
        internal static void AnimateProgress(ElegantProgressBar progress, double target)
        {
            if (progress == null) return;
            progress.BeginAnimation(ElegantProgressBar.ValueProperty, new DoubleAnimation(target, TimeSpan.FromMilliseconds(280)) { EasingFunction = EaseOut() });
        }
        internal static void ButtonMouseEnter(object sender, MouseEventArgs args) { ScaleButton(sender as Button, 1.026, 120); }
        internal static void ButtonMouseLeave(object sender, MouseEventArgs args) { ScaleButton(sender as Button, 1.0, 130); }
        internal static void ButtonMouseDown(object sender, MouseButtonEventArgs args) { ScaleButton(sender as Button, 0.975, 70); }
        internal static void ButtonMouseUp(object sender, MouseButtonEventArgs args) { ScaleButton(sender as Button, 1.026, 95); }
        private static void ScaleButton(Button button, double target, int milliseconds)
        {
            if (button == null || !button.IsEnabled) return;
            var scale = button.RenderTransform as ScaleTransform;
            if (scale == null)
            {
                scale = new ScaleTransform(1, 1);
                button.RenderTransform = scale;
                button.RenderTransformOrigin = new Point(0.5, 0.5);
            }
            var animation = new DoubleAnimation(target, TimeSpan.FromMilliseconds(milliseconds)) { EasingFunction = EaseOut() };
            scale.BeginAnimation(ScaleTransform.ScaleXProperty, animation);
            scale.BeginAnimation(ScaleTransform.ScaleYProperty, animation);
        }
    }
}

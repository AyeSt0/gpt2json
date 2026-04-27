using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Forms;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Effects;
using System.Windows.Media.Imaging;
using System.Windows.Shapes;
using Brushes = System.Windows.Media.Brushes;
using Button = System.Windows.Controls.Button;
using MessageBox = System.Windows.MessageBox;
using TextBox = System.Windows.Controls.TextBox;
using WpfApplication = System.Windows.Application;
using WpfPath = System.Windows.Shapes.Path;
using WpfProgressBar = System.Windows.Controls.ProgressBar;

namespace GPT2JSON.ArtSetup
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            var app = new WpfApplication();            app.Run(new InstallerWindow());
        }
    }

    public sealed class InstallerWindow : Window
    {
        private const string AppName = "GPT2JSON";
        private const string Version = "v0.1.0";
        private readonly TextBox _dirBox;
        private readonly Button _installButton;
        private readonly WpfProgressBar _progress;
        private readonly TextBlock _status;
        private readonly Button _closeButton;
        private readonly Button _minButton;

        public InstallerWindow()
        {
            Title = AppName + " " + Version + " 安装";
            Width = 980;
            Height = 640;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;
            WindowStyle = WindowStyle.None;
            AllowsTransparency = true;
            ResizeMode = ResizeMode.NoResize;
            Background = Brushes.Transparent;
            Icon = LoadImage("GPT2JSON.Icon.png");
            SnapsToDevicePixels = true;
            UseLayoutRounding = true;
            NameScope.SetNameScope(this, new NameScope());

            var root = new Canvas();
            root.Width = 980;
            root.Height = 640;
            Content = root;

            AddBackdropRings(root);

            var outerGlow = new WpfPath
            {
                Data = OuterShellGeometry(),
                Stroke = new LinearGradientBrush(Color.FromArgb(190, 33, 210, 255), Color.FromArgb(150, 182, 75, 255), 8),
                StrokeThickness = 6,
                Fill = Brushes.Transparent,
                Opacity = 0.52,
                Effect = new BlurEffect { Radius = 7 }
            };
            Canvas.SetLeft(outerGlow, 40);
            Canvas.SetTop(outerGlow, 40);
            root.Children.Add(outerGlow);

            var main = new WpfPath
            {
                Data = OuterShellGeometry(),
                Fill = new LinearGradientBrush(
                    Color.FromArgb(252, 5, 13, 36),
                    Color.FromArgb(248, 9, 21, 53),
                    36),
                Stroke = new SolidColorBrush(Color.FromArgb(165, 118, 171, 255)),
                StrokeThickness = 1.2,
                Effect = new DropShadowEffect
                {
                    BlurRadius = 42,
                    ShadowDepth = 0,
                    Opacity = 0.55,
                    Color = Color.FromRgb(0, 0, 0)
                }
            };
            Canvas.SetLeft(main, 40);
            Canvas.SetTop(main, 40);
            root.Children.Add(main);

            var shell = new Grid
            {
                Width = 900,
                Height = 560,
                Clip = OuterShellGeometry(),
                Background = Brushes.Transparent
            };
            Canvas.SetLeft(shell, 40);
            Canvas.SetTop(shell, 40);
            root.Children.Add(shell);
            shell.MouseLeftButtonDown += delegate(object sender, MouseButtonEventArgs args)
            {
                if (args.ChangedButton == MouseButton.Left)
                {
                    try { DragMove(); } catch { }
                }
            };

            AddIrregularBrandPanel(shell);
            AddGlowGrain(shell);

            var content = new Grid { Margin = new Thickness(332, 0, 42, 0) };
            shell.Children.Add(content);
            content.RowDefinitions.Add(new RowDefinition { Height = new GridLength(82) });
            content.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
            content.RowDefinitions.Add(new RowDefinition { Height = new GridLength(105) });

            var top = BuildTopBar();
            Grid.SetRow(top, 0);
            content.Children.Add(top);

            var center = BuildCenterPanel();
            Grid.SetRow(center, 1);
            content.Children.Add(center);

            var bottom = BuildBottomBar();
            Grid.SetRow(bottom, 2);
            content.Children.Add(bottom);

            _dirBox = FindName("InstallPathBox") as TextBox;
            _installButton = FindName("InstallButton") as Button;
            _progress = FindName("InstallProgress") as WpfProgressBar;
            _status = FindName("StatusText") as TextBlock;
            _closeButton = FindName("CloseButton") as Button;
            _minButton = FindName("MinButton") as Button;

            if (_dirBox != null)
                _dirBox.Text = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "GPT2JSON");
            if (_installButton != null)
                _installButton.Click += async delegate { await InstallAsync(); };
            if (_closeButton != null)
                _closeButton.Click += delegate { Close(); };
            if (_minButton != null)
                _minButton.Click += delegate { WindowState = WindowState.Minimized; };
        }

        private Geometry OuterShellGeometry()
        {
            // Visible window silhouette, in the 900x560 local coordinate system.
            // It deliberately avoids a rectangular installer frame: the left brand island
            // swells outward, the top edge forms a shallow valley, and the bottom edge
            // floats like a liquid glass plate.
            return Geometry.Parse(
                "M124,0 " +
                "C70,-14 28,18 18,68 " +
                "C7,122 42,145 30,196 " +
                "C17,254 -20,291 18,348 " +
                "C55,404 8,454 36,512 " +
                "C58,558 113,566 169,548 " +
                "C224,531 270,552 326,560 " +
                "L514,560 " +
                "C590,534 648,544 720,560 " +
                "L840,560 " +
                "C879,560 900,538 900,498 " +
                "L900,64 " +
                "C900,22 876,0 834,0 " +
                "L644,0 " +
                "C584,18 527,32 472,8 " +
                "C434,-10 399,0 365,25 " +
                "C329,52 290,39 257,14 " +
                "C220,-13 168,10 124,0 Z");
        }

        private void AddBackdropRings(Canvas root)
        {
            var ring1 = new WpfPath
            {
                Data = Geometry.Parse("M58,470 C185,150 520,24 780,168 C966,270 948,500 710,586 C485,668 198,596 58,470 Z"),
                StrokeThickness = 18,
                Stroke = new LinearGradientBrush(Color.FromRgb(28, 211, 255), Color.FromRgb(160, 73, 255), 30),
                Fill = Brushes.Transparent,
                Opacity = 0.62,
                Effect = new BlurEffect { Radius = 5 }
            };
            root.Children.Add(ring1);

            var ring2 = new WpfPath
            {
                Data = Geometry.Parse("M675,44 C910,86 1012,246 930,394 C842,556 560,614 310,552 C190,520 110,466 76,410"),
                StrokeThickness = 24,
                StrokeStartLineCap = PenLineCap.Round,
                StrokeEndLineCap = PenLineCap.Round,
                Stroke = new LinearGradientBrush(Color.FromArgb(210, 43, 204, 255), Color.FromArgb(170, 180, 77, 255), 0),
                Fill = Brushes.Transparent,
                Opacity = 0.54,
                Effect = new BlurEffect { Radius = 8 }
            };
            root.Children.Add(ring2);

            var comet = new WpfPath
            {
                Data = Geometry.Parse("M792,42 C934,94 996,194 945,310"),
                StrokeThickness = 34,
                StrokeStartLineCap = PenLineCap.Round,
                StrokeEndLineCap = PenLineCap.Round,
                Stroke = new LinearGradientBrush(Color.FromArgb(160, 30, 213, 255), Color.FromArgb(0, 174, 82, 255), 0),
                Fill = Brushes.Transparent,
                Opacity = 0.62,
                Effect = new BlurEffect { Radius = 11 }
            };
            root.Children.Add(comet);

            var lowerComet = new WpfPath
            {
                Data = Geometry.Parse("M122,580 C330,642 610,640 800,548"),
                StrokeThickness = 16,
                StrokeStartLineCap = PenLineCap.Round,
                StrokeEndLineCap = PenLineCap.Round,
                Stroke = new LinearGradientBrush(Color.FromArgb(160, 166, 70, 255), Color.FromArgb(80, 25, 209, 255), 0),
                Fill = Brushes.Transparent,
                Opacity = 0.58,
                Effect = new BlurEffect { Radius = 6 }
            };
            root.Children.Add(lowerComet);

            var aura = new Ellipse
            {
                Width = 780,
                Height = 520,
                Fill = new RadialGradientBrush(Color.FromArgb(80, 62, 151, 255), Color.FromArgb(0, 1, 7, 21)),
                Opacity = 0.55
            };
            Canvas.SetLeft(aura, 120);
            Canvas.SetTop(aura, 65);
            root.Children.Insert(0, aura);
        }

        private void AddIrregularBrandPanel(Grid shell)
        {
            var brandPath = new WpfPath
            {
                Data = Geometry.Parse("M0,0 L292,0 C322,54 288,118 306,178 C330,259 282,324 306,402 C326,468 292,526 318,560 L0,560 Z"),
                Fill = new ImageBrush(LoadImage("GPT2JSON.Side.png"))
                {
                    Stretch = Stretch.UniformToFill,
                    AlignmentX = AlignmentX.Left,
                    AlignmentY = AlignmentY.Center
                }
            };
            shell.Children.Add(brandPath);

            var wave = new WpfPath
            {
                Data = Geometry.Parse("M287,0 C326,62 289,126 310,192 C337,276 281,344 311,424 C331,482 296,531 322,560"),
                StrokeThickness = 2.0,
                Stroke = new LinearGradientBrush(Color.FromArgb(210, 255, 255, 255), Color.FromArgb(20, 255, 255, 255), 90),
                Fill = Brushes.Transparent,
                Opacity = 0.88
            };
            shell.Children.Add(wave);

            var logo = new Border
            {
                Width = 58,
                Height = 58,
                CornerRadius = new CornerRadius(17),
                BorderThickness = new Thickness(1),
                BorderBrush = new SolidColorBrush(Color.FromArgb(115, 128, 213, 255)),
                Background = new ImageBrush(LoadImage("GPT2JSON.Icon.png")) { Stretch = Stretch.UniformToFill },
                Margin = new Thickness(34, 34, 0, 0),
                HorizontalAlignment = System.Windows.HorizontalAlignment.Left,
                VerticalAlignment = System.Windows.VerticalAlignment.Top,
                Effect = new DropShadowEffect { BlurRadius = 18, ShadowDepth = 0, Color = Color.FromRgb(31, 180, 255), Opacity = 0.34 }
            };
            shell.Children.Add(logo);

            var title = new TextBlock
            {
                Text = "GPT2JSON",
                Foreground = Brushes.White,
                FontSize = 32,
                FontWeight = FontWeights.Bold,
                Margin = new Thickness(34, 104, 0, 0),
                Effect = new DropShadowEffect { BlurRadius = 18, ShadowDepth = 0, Color = Color.FromRgb(35, 162, 255), Opacity = 0.28 }
            };
            shell.Children.Add(title);

            var sub = new TextBlock
            {
                Text = "Sub2API / CPA JSON 导出工具",
                Foreground = new SolidColorBrush(Color.FromRgb(184, 205, 236)),
                FontSize = 14,
                Margin = new Thickness(36, 148, 0, 0)
            };
            shell.Children.Add(sub);

            var version = new Border
            {
                CornerRadius = new CornerRadius(12),
                Background = new SolidColorBrush(Color.FromArgb(45, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(80, 255, 255, 255)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(12, 5, 12, 5),
                HorizontalAlignment = System.Windows.HorizontalAlignment.Left,
                VerticalAlignment = System.Windows.VerticalAlignment.Bottom,
                Margin = new Thickness(34, 0, 0, 34),
                Child = new TextBlock
                {
                    Text = Version,
                    Foreground = new SolidColorBrush(Color.FromRgb(210, 225, 255)),
                    FontSize = 13,
                    FontWeight = FontWeights.SemiBold
                }
            };
            shell.Children.Add(version);
        }

        private void AddGlowGrain(Grid shell)
        {
            var dotBrush = new RadialGradientBrush(Color.FromArgb(88, 69, 224, 255), Color.FromArgb(0, 69, 224, 255));
            int[] xs = { 410, 488, 560, 642, 735, 805, 476, 682 };
            int[] ys = { 118, 88, 154, 104, 170, 96, 455, 430 };
            for (int i = 0; i < xs.Length; i++)
            {
                var e = new Ellipse { Width = 90, Height = 90, Fill = dotBrush, Opacity = 0.28 };
                e.Margin = new Thickness(xs[i], ys[i], 0, 0);
                shell.Children.Add(e);
            }
        }

        private UIElement BuildTopBar()
        {
            var grid = new Grid { Margin = new Thickness(0, 30, 0, 0) };
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(94) });

            var badge = new Border
            {
                HorizontalAlignment = System.Windows.HorizontalAlignment.Left,
                VerticalAlignment = System.Windows.VerticalAlignment.Top,
                Padding = new Thickness(12, 6, 12, 6),
                CornerRadius = new CornerRadius(16),
                Background = new SolidColorBrush(Color.FromArgb(38, 90, 180, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(80, 87, 197, 255)),
                BorderThickness = new Thickness(1),
                Child = new TextBlock
                {
                    Text = "艺术安装器 · " + Version,
                    Foreground = new SolidColorBrush(Color.FromRgb(174, 212, 255)),
                    FontSize = 12,
                    FontWeight = FontWeights.SemiBold
                }
            };
            grid.Children.Add(badge);

            var buttons = new StackPanel { Orientation = System.Windows.Controls.Orientation.Horizontal, HorizontalAlignment = System.Windows.HorizontalAlignment.Right };
            RegisterName("MinButton", WindowButton("—"));
            RegisterName("CloseButton", WindowButton("×"));
            buttons.Children.Add((Button)FindName("MinButton"));
            buttons.Children.Add((Button)FindName("CloseButton"));
            Grid.SetColumn(buttons, 1);
            grid.Children.Add(buttons);
            return grid;
        }

        private UIElement BuildCenterPanel()
        {
            var panel = new StackPanel { VerticalAlignment = System.Windows.VerticalAlignment.Center };

            var title = new TextBlock
            {
                Text = "GPT2JSON 安装",
                Foreground = Brushes.White,
                FontSize = 42,
                FontWeight = FontWeights.Bold,            };
            panel.Children.Add(title);

            var desc = new TextBlock
            {
                Text = "轻量独立的 Sub2API / CPA JSON 导出工具",
                Foreground = new SolidColorBrush(Color.FromRgb(161, 179, 214)),
                FontSize = 16,
                Margin = new Thickness(2, 8, 0, 24)
            };
            panel.Children.Add(desc);

            var features = new WrapPanel { Margin = new Thickness(0, 0, 0, 26) };
            features.Children.Add(FeaturePill("协议优先"));
            features.Children.Add(FeaturePill("批量导出"));
            features.Children.Add(FeaturePill("本地处理"));
            panel.Children.Add(features);

            var label = new TextBlock
            {
                Text = "安装位置",
                Foreground = new SolidColorBrush(Color.FromRgb(231, 240, 255)),
                FontSize = 15,
                FontWeight = FontWeights.SemiBold,
                Margin = new Thickness(0, 0, 0, 10)
            };
            panel.Children.Add(label);

            var pathBorder = new Border
            {
                Height = 58,
                CornerRadius = new CornerRadius(18),
                Background = new SolidColorBrush(Color.FromArgb(62, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(95, 142, 195, 255)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(18, 0, 10, 0)
            };
            var pathGrid = new Grid();
            pathGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            pathGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(96) });
            var box = new TextBox
            {
                Name = "InstallPathBox",
                Foreground = new SolidColorBrush(Color.FromRgb(225, 238, 255)),
                Background = Brushes.Transparent,
                BorderThickness = new Thickness(0),
                FontSize = 15,
                VerticalContentAlignment = System.Windows.VerticalAlignment.Center,
                CaretBrush = Brushes.White
            };
            RegisterName(box.Name, box);
            pathGrid.Children.Add(box);
            var browse = new Button
            {
                Content = "浏览",
                Height = 40,
                Margin = new Thickness(10, 8, 0, 8),
                Background = new SolidColorBrush(Color.FromArgb(55, 96, 165, 255)),
                Foreground = Brushes.White,
                BorderBrush = new SolidColorBrush(Color.FromArgb(100, 160, 205, 255)),
                Style = RoundedButtonStyle(12)
            };
            browse.Click += BrowsePath;
            Grid.SetColumn(browse, 1);
            pathGrid.Children.Add(browse);
            pathBorder.Child = pathGrid;
            panel.Children.Add(pathBorder);

            RegisterProgress(panel);
            return panel;
        }

        private UIElement BuildBottomBar()
        {
            var grid = new Grid { Margin = new Thickness(0, 0, 0, 24) };
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(160) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(18) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(132) });

            var install = new Button
            {
                Name = "InstallButton",
                Content = "开始安装",
                Height = 54,
                FontSize = 17,
                FontWeight = FontWeights.Bold,
                Foreground = Brushes.White,
                Background = new LinearGradientBrush(Color.FromRgb(27, 181, 255), Color.FromRgb(176, 69, 255), 0),
                BorderBrush = new SolidColorBrush(Color.FromArgb(135, 202, 232, 255)),
                Style = RoundedButtonStyle(18)
            };
            RegisterName(install.Name, install);
            Grid.SetColumn(install, 1);
            grid.Children.Add(install);

            var cancel = new Button
            {
                Content = "取消",
                Height = 54,
                FontSize = 15,
                Foreground = new SolidColorBrush(Color.FromRgb(218, 230, 255)),
                Background = new SolidColorBrush(Color.FromArgb(28, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(86, 163, 190, 255)),
                Style = RoundedButtonStyle(18)
            };
            cancel.Click += delegate { Close(); };
            Grid.SetColumn(cancel, 3);
            grid.Children.Add(cancel);
            return grid;
        }

        private Border FeaturePill(string text)
        {
            return new Border
            {
                CornerRadius = new CornerRadius(14),
                Padding = new Thickness(12, 7, 12, 7),
                Margin = new Thickness(0, 0, 10, 8),
                Background = new SolidColorBrush(Color.FromArgb(36, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(55, 130, 204, 255)),
                BorderThickness = new Thickness(1),
                Child = new TextBlock
                {
                    Text = text,
                    Foreground = new SolidColorBrush(Color.FromRgb(195, 220, 255)),
                    FontSize = 13,
                    FontWeight = FontWeights.SemiBold
                }
            };
        }

        private bool RegisterProgress(StackPanel panel)
        {
            var progress = new WpfProgressBar
            {
                Name = "InstallProgress",
                Height = 5,
                Minimum = 0,
                Maximum = 100,
                Value = 0,
                Margin = new Thickness(0, 22, 0, 0),
                Foreground = new SolidColorBrush(Color.FromRgb(54, 210, 255)),
                Background = new SolidColorBrush(Color.FromArgb(28, 255, 255, 255)),
                BorderThickness = new Thickness(0)
            };
            RegisterName(progress.Name, progress);
            panel.Children.Add(progress);

            var status = new TextBlock
            {
                Name = "StatusText",
                Text = "准备就绪：选择目录后即可开始安装。",
                Foreground = new SolidColorBrush(Color.FromRgb(137, 158, 196)),
                FontSize = 12,
                Margin = new Thickness(2, 10, 0, 0)
            };
            RegisterName(status.Name, status);
            panel.Children.Add(status);
            return true;
        }

        private Button WindowButton(string text)
        {
            return new Button
            {
                Content = text,
                Width = 38,
                Height = 32,
                Margin = new Thickness(4, 0, 0, 0),
                Foreground = new SolidColorBrush(Color.FromRgb(217, 229, 255)),
                Background = Brushes.Transparent,
                BorderBrush = Brushes.Transparent,
                FontSize = text == "×" ? 20 : 15,
                Style = RoundedButtonStyle(10)
            };
        }

        private Style RoundedButtonStyle(double radius)
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
            return style;
        }

        private void BrowsePath(object sender, RoutedEventArgs e)
        {
            using (var dlg = new FolderBrowserDialog())
            {
                dlg.Description = "选择 GPT2JSON 安装目录";
                dlg.SelectedPath = _dirBox != null ? _dirBox.Text : string.Empty;
                if (dlg.ShowDialog() == System.Windows.Forms.DialogResult.OK && _dirBox != null)
                    _dirBox.Text = dlg.SelectedPath;
            }
        }

        private async Task InstallAsync()
        {
            if (_dirBox == null || string.IsNullOrWhiteSpace(_dirBox.Text))
            {
                MessageBox.Show("请先选择安装目录。", AppName, MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            SetBusy(true, "正在释放安装核心…", 18);
            try
            {
                string installerPath = ExtractInstaller();
                Directory.CreateDirectory(_dirBox.Text);
                SetBusy(true, "安装核心已就绪，正在写入文件…", 42);
                int code = await Task.Run(delegate
                {
                    var psi = new ProcessStartInfo
                    {
                        FileName = installerPath,
                        Arguments = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR=\"" + _dirBox.Text + "\"",
                        UseShellExecute = false,
                        CreateNoWindow = true
                    };
                    var p = Process.Start(psi);
                    p.WaitForExit();
                    return p.ExitCode;
                });

                if (code != 0)
                    throw new InvalidOperationException("安装核心返回错误码：" + code);

                SetBusy(false, "安装完成：GPT2JSON 已准备好。", 100);
                TryLaunchInstalledApp();
            }
            catch (Exception ex)
            {
                SetBusy(false, "安装失败：" + ex.Message, 0);
                MessageBox.Show(ex.Message, AppName + " 安装失败", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void SetBusy(bool busy, string text, double progress)
        {
            if (_installButton != null) _installButton.IsEnabled = !busy;
            if (_dirBox != null) _dirBox.IsEnabled = !busy;
            if (_status != null) _status.Text = text;
            if (_progress != null) _progress.Value = progress;
        }

        private string ExtractInstaller()
        {
            string dir = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "GPT2JSON-ArtSetup", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(dir);
            string path = System.IO.Path.Combine(dir, "GPT2JSON-Setup-v0.1.0.exe");
            using (var input = Assembly.GetExecutingAssembly().GetManifestResourceStream("GPT2JSON.Setup.exe"))
            {
                if (input == null) throw new FileNotFoundException("未找到内嵌安装核心。", "GPT2JSON.Setup.exe");
                using (var output = File.Create(path))
                {
                    input.CopyTo(output);
                }
            }
            return path;
        }

        private void TryLaunchInstalledApp()
        {
            try
            {
                string exe = System.IO.Path.Combine(_dirBox.Text, "GPT2JSON.exe");
                if (File.Exists(exe))
                    Process.Start(new ProcessStartInfo { FileName = exe, UseShellExecute = true });
            }
            catch { }
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
}





